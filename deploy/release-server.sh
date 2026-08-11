#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

APP_ROOT="/opt/wind-doc-system"
RELEASES_ROOT="/opt/wind-doc-releases"
SHARED_ROOT="/opt/wind-doc-shared"
SHARED_ENV="${SHARED_ROOT}/backend.env.production"
PIP_CACHE_DIR="${SHARED_ROOT}/pip-cache"
LOCK_FILE="/run/lock/wind-doc-system-release.lock"
WEB_SERVICE="wind-doc-system"
WORKER_SERVICE="wind-doc-worker"

ACTION="${1:-}"
if [[ -z "${ACTION}" ]]; then
  echo "Usage: $0 deploy|rollback [options]" >&2
  exit 2
fi
shift

ARCHIVE=""
FRONTEND_ENV_SOURCE=""
RELEASE_ID=""
TARGET_RELEASE=""
DOMAIN=""
KEEP_RELEASES="5"
ALLOW_MIGRATIONS="false"
DOCUMENT_AGENT_ENABLED="true"
SOURCE_COMMIT="unknown"
SOURCE_DIRTY="false"

while (($#)); do
  case "$1" in
    --archive) ARCHIVE="${2:?missing archive}"; shift 2 ;;
    --frontend-env) FRONTEND_ENV_SOURCE="${2:?missing frontend env}"; shift 2 ;;
    --release) RELEASE_ID="${2:?missing release}"; shift 2 ;;
    --target) TARGET_RELEASE="${2:?missing target}"; shift 2 ;;
    --domain) DOMAIN="${2:?missing domain}"; shift 2 ;;
    --keep) KEEP_RELEASES="${2:?missing keep count}"; shift 2 ;;
    --allow-migrations) ALLOW_MIGRATIONS="${2:?missing allow-migrations}"; shift 2 ;;
    --document-agent-enabled) DOCUMENT_AGENT_ENABLED="${2:?missing feature flag}"; shift 2 ;;
    --source-commit) SOURCE_COMMIT="${2:?missing commit}"; shift 2 ;;
    --source-dirty) SOURCE_DIRTY="${2:?missing dirty flag}"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ "${EUID}" -eq 0 ]] || fail "This script must run as root"
[[ "${ACTION}" == "deploy" || "${ACTION}" == "rollback" ]] || fail "Invalid action: ${ACTION}"
[[ "${DOMAIN}" =~ ^[A-Za-z0-9.-]+$ ]] || fail "Invalid domain"
[[ "${KEEP_RELEASES}" =~ ^[0-9]+$ ]] || fail "Invalid keep count"
((KEEP_RELEASES >= 2 && KEEP_RELEASES <= 20)) || fail "Keep count must be between 2 and 20"
[[ "${ALLOW_MIGRATIONS}" == "true" || "${ALLOW_MIGRATIONS}" == "false" ]] || fail "Invalid migration flag"
[[ "${DOCUMENT_AGENT_ENABLED}" == "true" || "${DOCUMENT_AGENT_ENABLED}" == "false" ]] || fail "Invalid feature flag"
[[ "${SOURCE_DIRTY}" == "true" || "${SOURCE_DIRTY}" == "false" ]] || fail "Invalid dirty flag"
[[ "${SOURCE_COMMIT}" == "unknown" || "${SOURCE_COMMIT}" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid source commit"

for command_name in flock realpath systemctl runuser curl tar nginx python3 npm; do
  command -v "${command_name}" >/dev/null || fail "Missing command: ${command_name}"
done

exec 9>"${LOCK_FILE}"
flock -n 9 || fail "Another deployment or rollback is already running"

mkdir -p "${RELEASES_ROOT}" "${SHARED_ROOT}" "${PIP_CACHE_DIR}"
chmod 0755 "${RELEASES_ROOT}"
chown root:winddoc "${SHARED_ROOT}"
chmod 0750 "${SHARED_ROOT}"

# X-Accel-Redirect serves authorized downloads through the www-data Nginx
# worker. Keep the storage tree private while repairing legacy directories
# whose old winddoc group prevents Nginx from traversing to otherwise valid
# files. The setgid bit makes newly created shard directories inherit the
# www-data group across both the web and worker services.
DOCUMENT_STORAGE_ROOT="/data/documents"
mkdir -p "${DOCUMENT_STORAGE_ROOT}"
chown winddoc:www-data "${DOCUMENT_STORAGE_ROOT}"
find "${DOCUMENT_STORAGE_ROOT}" -xdev -type d \
  \( ! -group www-data -o ! -perm 2750 \) \
  -exec chgrp www-data {} + -exec chmod 2750 {} +
find "${DOCUMENT_STORAGE_ROOT}" -xdev -type f \
  \( ! -group www-data -o ! -perm 0640 \) \
  -exec chgrp www-data {} + -exec chmod 0640 {} +

WINDDOC_HOME="$(getent passwd winddoc | cut -d: -f6)"
[[ -n "${WINDDOC_HOME}" && -d "${WINDDOC_HOME}" ]] || WINDDOC_HOME="/opt/wind_doc_manage_system"

if [[ ! -e "${PIP_CACHE_DIR}/.seeded" ]]; then
  if [[ -d "/root/.cache/pip" ]]; then
    cp -a /root/.cache/pip/. "${PIP_CACHE_DIR}/"
  fi
  if [[ -d "${WINDDOC_HOME}/.cache/pip" ]]; then
    cp -a "${WINDDOC_HOME}/.cache/pip/." "${PIP_CACHE_DIR}/"
  fi
  touch "${PIP_CACHE_DIR}/.seeded"
fi
chown -R winddoc:winddoc "${PIP_CACHE_DIR}"
chmod 0750 "${PIP_CACHE_DIR}"

run_winddoc() {
  runuser -u winddoc -- env \
    HOME="${WINDDOC_HOME}" \
    PATH="/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    DJANGO_SETTINGS_MODULE="config.settings.production" \
    PIP_CACHE_DIR="${PIP_CACHE_DIR}" \
    PIP_DEFAULT_TIMEOUT="120" \
    VITE_DOCUMENT_AGENT_ENABLED="${DOCUMENT_AGENT_ENABLED}" \
    "$@"
}

RECOVERY_ACTIVE="false"
RECOVERY_TARGET=""

recover_after_error() {
  local exit_code="$?"
  trap - ERR
  if [[ "${RECOVERY_ACTIVE}" == "true" ]]; then
    echo "Deployment interrupted; restoring the prior service state..." >&2
    if [[ -n "${RECOVERY_TARGET}" && -d "${RECOVERY_TARGET}" ]]; then
      if [[ -L "${APP_ROOT}" || ! -e "${APP_ROOT}" ]]; then
        activate_symlink "${RECOVERY_TARGET}" || true
        install_units "${RECOVERY_TARGET}" || true
      fi
    fi
    restart_services || true
    health_check || true
  fi
  exit "${exit_code}"
}

trap recover_after_error ERR

current_target() {
  if [[ -L "${APP_ROOT}" ]]; then
    readlink -f "${APP_ROOT}"
  elif [[ -d "${APP_ROOT}" ]]; then
    realpath "${APP_ROOT}"
  else
    return 1
  fi
}

validate_release_path() {
  local candidate resolved
  candidate="$1"
  resolved="$(realpath -e "${candidate}")" || fail "Release does not exist: ${candidate}"
  case "${resolved}" in
    "${RELEASES_ROOT}"/*) ;;
    *) fail "Release is outside ${RELEASES_ROOT}: ${resolved}" ;;
  esac
  [[ -d "${resolved}/backend" && -d "${resolved}/fronted/dist" && -x "${resolved}/venv/bin/python" ]] \
    || fail "Release is incomplete: ${resolved}"
  printf '%s\n' "${resolved}"
}

install_units() {
  local target="$1"
  install -o root -g root -m 0644 "${target}/deploy/systemd/wind-doc-system.service" \
    "/etc/systemd/system/wind-doc-system.service"
  install -o root -g root -m 0644 "${target}/deploy/systemd/wind-doc-worker.service" \
    "/etc/systemd/system/wind-doc-worker.service"
  systemctl daemon-reload
}

activate_symlink() {
  local target="$1" temporary_link
  temporary_link="/opt/.wind-doc-system.next.$$"
  rm -f -- "${temporary_link}"
  ln -s "${target}" "${temporary_link}"
  if [[ -L "${APP_ROOT}" ]]; then
    mv -Tf "${temporary_link}" "${APP_ROOT}"
  elif [[ ! -e "${APP_ROOT}" ]]; then
    mv -T "${temporary_link}" "${APP_ROOT}"
  else
    rm -f -- "${temporary_link}"
    fail "Cannot replace non-symlink application root"
  fi
}

restart_services() {
  systemctl restart "${WEB_SERVICE}" "${WORKER_SERVICE}"
  systemctl is-active --quiet "${WEB_SERVICE}"
  systemctl is-active --quiet "${WORKER_SERVICE}"
}

health_check() {
  local attempt
  nginx -t
  for attempt in $(seq 1 15); do
    if curl --silent --show-error --fail \
      --connect-timeout 3 --max-time 10 \
      --resolve "${DOMAIN}:443:127.0.0.1" \
      "https://${DOMAIN}/" >/dev/null \
      && curl --silent --show-error --fail \
        --connect-timeout 3 --max-time 10 \
        --resolve "${DOMAIN}:443:127.0.0.1" \
        "https://${DOMAIN}/api/v1/auth/csrf/" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

write_release_state() {
  local current="$1" previous="$2"
  printf '%s\n' "${current}" > "${RELEASES_ROOT}/.current"
  printf '%s\n' "${previous}" > "${RELEASES_ROOT}/.previous"
  chmod 0640 "${RELEASES_ROOT}/.current" "${RELEASES_ROOT}/.previous"
}

cleanup_old_releases() {
  local current previous candidate resolved index
  current="$(cat "${RELEASES_ROOT}/.current" 2>/dev/null || true)"
  previous="$(cat "${RELEASES_ROOT}/.previous" 2>/dev/null || true)"
  index=0
  while IFS= read -r candidate; do
    [[ -n "${candidate}" ]] || continue
    resolved="$(realpath -e "${candidate}")" || continue
    [[ "${resolved}" == "${current}" || "${resolved}" == "${previous}" ]] && continue
    index=$((index + 1))
    if ((index > KEEP_RELEASES - 2)); then
      case "${resolved}" in
        "${RELEASES_ROOT}"/*) rm -rf -- "${resolved}" ;;
        *) fail "Refusing to remove unexpected path: ${resolved}" ;;
      esac
    fi
  done < <(find "${RELEASES_ROOT}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
    | sort -nr | cut -d' ' -f2-)
}

bootstrap_shared_env() {
  local source_env env_line
  if [[ ! -f "${SHARED_ENV}" ]]; then
    source_env="${APP_ROOT}/backend/.env.production"
    [[ -f "${source_env}" ]] || fail "Production environment file not found: ${source_env}"
    install -o winddoc -g winddoc -m 0600 "${source_env}" "${SHARED_ENV}"
  fi

  [[ -f "${FRONTEND_ENV_SOURCE}" ]] || fail "Frontend production environment file not found"
  while IFS= read -r env_line || [[ -n "${env_line}" ]]; do
    env_line="${env_line%$'\r'}"
    [[ -z "${env_line}" || "${env_line}" =~ ^[[:space:]]*# ]] && continue
    [[ "${env_line}" =~ ^VITE_[A-Z0-9_]+= ]] || fail "Frontend environment contains a non-VITE variable"
  done < "${FRONTEND_ENV_SOURCE}"
  install -o winddoc -g winddoc -m 0600 "${FRONTEND_ENV_SOURCE}" \
    "${SHARED_ROOT}/fronted.env.production"
}

prepare_release() {
  local release_dir="$1" archive_entry migration_plan current_release
  [[ -f "${ARCHIVE}" ]] || fail "Archive not found: ${ARCHIVE}"
  [[ ! -e "${release_dir}" ]] || fail "Release already exists: ${release_dir}"

  while IFS= read -r archive_entry; do
    [[ "${archive_entry}" != /* ]] || fail "Archive contains an absolute path"
    case "/${archive_entry}/" in
      */../*) fail "Archive contains a parent traversal path" ;;
    esac
  done < <(tar -tzf "${ARCHIVE}")

  mkdir -m 0750 "${release_dir}"
  tar -xzf "${ARCHIVE}" -C "${release_dir}"
  chown -R winddoc:winddoc "${release_dir}"

  rm -f -- "${release_dir}/backend/.env.production"
  ln -s "${SHARED_ENV}" "${release_dir}/backend/.env.production"
  rm -f -- "${release_dir}/fronted/.env.production" "${release_dir}/fronted/.env.local"
  ln -s "${SHARED_ROOT}/fronted.env.production" "${release_dir}/fronted/.env.production"

  current_release="$(current_target 2>/dev/null || true)"
  if [[ -n "${current_release}" && -x "${current_release}/venv/bin/python" ]]; then
    echo "Seeding the release virtual environment from ${current_release}/venv"
    run_winddoc cp -a "${current_release}/venv" "${release_dir}/venv"
  else
    run_winddoc python3 -m venv "${release_dir}/venv"
  fi

  if ! run_winddoc "${release_dir}/venv/bin/python" -m pip install \
    --disable-pip-version-check --no-index \
    --requirement "${release_dir}/backend/requirements/prod.txt"; then
    echo "Installed packages do not satisfy the release requirements; installing missing dependencies..."
    run_winddoc "${release_dir}/venv/bin/python" -m pip install \
      --disable-pip-version-check --prefer-binary --retries 5 \
      --requirement "${release_dir}/backend/requirements/prod.txt"
  fi
  run_winddoc "${release_dir}/venv/bin/python" -m pip freeze \
    > "${release_dir}/.release-python-packages.txt"

  run_winddoc npm --prefix "${release_dir}/fronted" ci
  run_winddoc npm --prefix "${release_dir}/fronted" run lint
  run_winddoc npm --prefix "${release_dir}/fronted" run type-check
  run_winddoc npm --prefix "${release_dir}/fronted" run test:unit
  run_winddoc npm --prefix "${release_dir}/fronted" run build
  run_winddoc npm --prefix "${release_dir}/fronted" audit --omit=dev
  rm -rf -- "${release_dir}/fronted/node_modules"

  (
    cd "${release_dir}/backend"
    run_winddoc "${release_dir}/venv/bin/python" manage.py check --deploy
    run_winddoc "${release_dir}/venv/bin/python" manage.py makemigrations --check --dry-run
    run_winddoc "${release_dir}/venv/bin/python" manage.py collectstatic --noinput
    migration_plan="$(run_winddoc "${release_dir}/venv/bin/python" manage.py migrate --plan)"
    printf '%s\n' "${migration_plan}" | tee "${release_dir}/.release-migration-plan.txt"
    if grep -q "No planned migration operations" <<<"${migration_plan}"; then
      printf 'false\n' > "${release_dir}/.release-has-migrations"
    else
      printf 'true\n' > "${release_dir}/.release-has-migrations"
    fi
  )

  chown winddoc:www-data "${release_dir}" "${release_dir}/fronted" "${release_dir}/backend"
  chmod 0750 "${release_dir}" "${release_dir}/fronted" "${release_dir}/backend"
  chgrp -R www-data "${release_dir}/fronted/dist" "${release_dir}/backend/staticfiles"
  chmod -R g+rX "${release_dir}/fronted/dist" "${release_dir}/backend/staticfiles"
  cat > "${release_dir}/.release-info" <<EOF
release=${RELEASE_ID}
commit=${SOURCE_COMMIT}
dirty=${SOURCE_DIRTY}
prepared_at=$(date --iso-8601=seconds)
EOF
  chown winddoc:winddoc "${release_dir}/.release-"*
}

deploy_release() {
  local release_dir previous legacy has_migrations
  [[ "${RELEASE_ID}" =~ ^[0-9]{8}-[0-9]{6}-[0-9a-f]{7,40}(-dirty)?$ ]] \
    || fail "Invalid release id"
  [[ -n "${ARCHIVE}" ]] || fail "--archive is required"
  [[ -n "${FRONTEND_ENV_SOURCE}" ]] || fail "--frontend-env is required"
  bootstrap_shared_env
  release_dir="${RELEASES_ROOT}/${RELEASE_ID}"
  prepare_release "${release_dir}"

  has_migrations="$(cat "${release_dir}/.release-has-migrations")"
  if [[ "${has_migrations}" == "true" && "${ALLOW_MIGRATIONS}" != "true" ]]; then
    fail "Pending migrations detected. Review .release-migration-plan.txt and rerun with migration approval."
  fi

  previous="$(current_target)"
  RECOVERY_ACTIVE="true"
  RECOVERY_TARGET="${previous}"
  systemctl stop "${WORKER_SERVICE}" "${WEB_SERVICE}"

  if [[ "${has_migrations}" == "true" ]]; then
    echo "Creating a verified pre-migration system backup..."
    (
      cd "${previous}/backend"
      run_winddoc "${previous}/venv/bin/python" manage.py create_system_backup --trigger manual
    ) | tee "${release_dir}/.release-backup.txt"
    (
      cd "${release_dir}/backend"
      run_winddoc "${release_dir}/venv/bin/python" manage.py migrate --noinput
    )
  fi

  if [[ ! -L "${APP_ROOT}" ]]; then
    legacy="${RELEASES_ROOT}/legacy-$(date +%Y%m%d-%H%M%S)"
    mv "${APP_ROOT}" "${legacy}"
    previous="${legacy}"
    RECOVERY_TARGET="${previous}"
    ln -s "${release_dir}" "${APP_ROOT}"
  else
    activate_symlink "${release_dir}"
  fi

  install_units "${release_dir}"
  if ! restart_services || ! health_check; then
    echo "New release failed health checks; rolling back to ${previous}" >&2
    activate_symlink "${previous}"
    install_units "${previous}"
    restart_services || true
    health_check || true
    printf 'health-check-failed\n' > "${release_dir}/.failed"
    if [[ "${has_migrations}" == "true" ]]; then
      echo "Database migrations were applied. The pre-migration backup path is recorded in ${release_dir}/.release-backup.txt" >&2
    fi
    RECOVERY_ACTIVE="false"
    exit 1
  fi

  RECOVERY_ACTIVE="false"
  write_release_state "${release_dir}" "${previous}"
  cleanup_old_releases
  rm -f -- "${ARCHIVE}"
  echo "DEPLOY_OK release=${RELEASE_ID} previous=${previous}"
}

rollback_release() {
  local old_current target
  [[ -L "${APP_ROOT}" ]] || fail "Rollback is available after the first release-based deployment"
  old_current="$(current_target)"
  if [[ -n "${TARGET_RELEASE}" ]]; then
    [[ "${TARGET_RELEASE}" =~ ^[A-Za-z0-9._-]+$ ]] || fail "Invalid target release"
    target="${RELEASES_ROOT}/${TARGET_RELEASE}"
  else
    target="$(cat "${RELEASES_ROOT}/.previous" 2>/dev/null || true)"
  fi
  [[ -n "${target}" ]] || fail "No previous release is recorded"
  target="$(validate_release_path "${target}")"
  [[ "${target}" != "${old_current}" ]] || fail "Target is already active"

  RECOVERY_ACTIVE="true"
  RECOVERY_TARGET="${old_current}"
  systemctl stop "${WORKER_SERVICE}" "${WEB_SERVICE}"
  activate_symlink "${target}"
  install_units "${target}"
  if ! restart_services || ! health_check; then
    echo "Rollback target failed health checks; restoring ${old_current}" >&2
    activate_symlink "${old_current}"
    install_units "${old_current}"
    restart_services || true
    health_check || true
    RECOVERY_ACTIVE="false"
    exit 1
  fi

  RECOVERY_ACTIVE="false"
  write_release_state "${target}" "${old_current}"
  echo "ROLLBACK_OK release=$(basename "${target}") previous=$(basename "${old_current}")"
}

case "${ACTION}" in
  deploy) deploy_release ;;
  rollback) rollback_release ;;
esac
