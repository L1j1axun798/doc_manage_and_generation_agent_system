import os
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_SECRET_KEY=(str, "unsafe-development-key-change-me"),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DJANGO_CORS_ALLOWED_ORIGINS=(list, []),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    DATABASE_URL=(str, f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
    FILE_STORAGE_ROOT=(str, "data/files"),
    TEMPORARY_STORAGE_ROOT=(str, "data/temporary"),
    SYSTEM_BACKUP_LOCAL_ROOT=(str, "data/backups"),
    SYSTEM_BACKUP_OFFSITE_ROOT=(str, ""),
    SYSTEM_BACKUP_RETENTION_DAYS=(int, 30),
    SYSTEM_BACKUP_MYSQLDUMP_BIN=(str, "mysqldump"),
    SYSTEM_BACKUP_MYSQL_BIN=(str, "mysql"),
    MAX_UPLOAD_SIZE_MB=(int, 200),
    TEMPORARY_GRANT_DEFAULT_HOURS=(int, 24),
    WEBAUTHN_RP_ID=(str, "localhost"),
    WEBAUTHN_RP_NAME=(str, "绿能信盾资料管理系统"),
    WEBAUTHN_ALLOWED_ORIGINS=(list, ["http://localhost:5174"]),
    WEBAUTHN_CHALLENGE_TTL_SECONDS=(int, 300),
    WEBAUTHN_ENROLLMENT_TICKET_TTL_SECONDS=(int, 1800),
    API_REQUIRE_WEBAUTHN_SESSION=(bool, True),
    API_ENFORCE_PASSWORD_CHANGE=(bool, True),
    LOGIN_THROTTLE_IP_RATE=(str, "20/min"),
    LOGIN_THROTTLE_ACCOUNT_RATE=(str, "5/min"),
    TRUST_PROXY_HEADERS=(bool, False),
    USE_X_ACCEL_REDIRECT=(bool, False),
    X_ACCEL_REDIRECT_PREFIX=(str, "/protected-files/"),
    TEMPORARY_GRANT_MAX_HOURS=(int, 168),
    TEMPORARY_GRANT_MAX_DOWNLOADS=(int, 20),
    ENABLE_DJANGO_ADMIN=(bool, True),
    ENABLE_API_DOCS=(bool, True),
    VALIDATE_UPLOAD_FILE_SIGNATURES=(bool, True),
    DJANGO_SECURE_HSTS_SECONDS=(int, 3600),
    DOCUMENT_AGENT_ENABLED=(bool, False),
    DOCUMENT_AGENT_PHASE5_APPROVED=(bool, False),
    DOCUMENT_AGENT_ALLOW_FAKE_PROVIDER=(bool, False),
    REDIS_URL=(str, "redis://127.0.0.1:6379/0"),
    DOCUMENT_AGENT_JOB_TIMEOUT_SECONDS=(int, 1800),
    DOCUMENT_AGENT_STALE_TASK_SECONDS=(int, 2100),
)
ENV_FILE_NAME = (
    ".env.production"
    if os.environ.get("DJANGO_SETTINGS_MODULE") == "config.settings.production"
    else ".env"
)
environ.Env.read_env(BASE_DIR / ENV_FILE_NAME)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "rest_framework",
    "django_rq",
    "apps.accounts",
    "apps.access",
    "apps.audit",
    "apps.documents",
    "apps.document_generation",
    "apps.folders",
    "apps.locations",
    "apps.notifications",
    "apps.projects",
    "apps.system",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "common.middleware.RequestIDMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}
if (
    DATABASES["default"]["ENGINE"] != "django.db.backends.mysql"
    and env("DJANGO_SETTINGS_MODULE", default="") != "config.settings.testing"
):
    raise ImproperlyConfigured("DATABASE_URL must point to MySQL outside testing settings.")
if DATABASES["default"]["ENGINE"] == "django.db.backends.mysql":
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"].update(
        {
            "charset": "utf8mb4",
            "init_command": (
                "SET sql_mode='STRICT_TRANS_TABLES', transaction_isolation='READ-COMMITTED'"
            ),
        }
    )

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

CORS_ALLOWED_ORIGINS = env("DJANGO_CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "common.authentication.SecureSessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "login_ip": env("LOGIN_THROTTLE_IP_RATE"),
        "login_account": env("LOGIN_THROTTLE_ACCOUNT_RATE"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "风电检测资料管理系统 API",
    "DESCRIPTION": "公司内网资料管理系统后端 API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "UserRoleEnum": [
            ("system_admin", "系统管理员"),
            ("project_manager", "项目负责人"),
            ("data_operator", "资料整理员"),
            ("temporary_user", "临时用户"),
        ],
        "ProjectStatusEnum": [
            ("active", "进行中"),
            ("archived", "已归档"),
        ],
        "ProjectMemberRoleEnum": [
            ("manager", "负责人"),
            ("operator", "资料整理员"),
            ("viewer", "查看者"),
        ],
        "LocationReportStatusEnum": [
            ("success", "定位成功"),
            ("locate_failed", "定位失败"),
        ],
    },
}

FILE_STORAGE_ROOT = BASE_DIR / env("FILE_STORAGE_ROOT")
TEMPORARY_STORAGE_ROOT = BASE_DIR / env("TEMPORARY_STORAGE_ROOT")
SYSTEM_BACKUP_LOCAL_ROOT = BASE_DIR / env("SYSTEM_BACKUP_LOCAL_ROOT")
SYSTEM_BACKUP_OFFSITE_ROOT_VALUE = env("SYSTEM_BACKUP_OFFSITE_ROOT")
SYSTEM_BACKUP_OFFSITE_ROOT = (
    Path(SYSTEM_BACKUP_OFFSITE_ROOT_VALUE) if SYSTEM_BACKUP_OFFSITE_ROOT_VALUE else None
)
SYSTEM_BACKUP_RETENTION_DAYS = env("SYSTEM_BACKUP_RETENTION_DAYS")
SYSTEM_BACKUP_MYSQLDUMP_BIN = env("SYSTEM_BACKUP_MYSQLDUMP_BIN")
SYSTEM_BACKUP_MYSQL_BIN = env("SYSTEM_BACKUP_MYSQL_BIN")
MAX_UPLOAD_SIZE_BYTES = env("MAX_UPLOAD_SIZE_MB") * 1024 * 1024
TEMPORARY_GRANT_DEFAULT_HOURS = env("TEMPORARY_GRANT_DEFAULT_HOURS")
WEBAUTHN_RP_ID = env("WEBAUTHN_RP_ID")
WEBAUTHN_RP_NAME = env("WEBAUTHN_RP_NAME")
WEBAUTHN_ALLOWED_ORIGINS = env("WEBAUTHN_ALLOWED_ORIGINS")
WEBAUTHN_CHALLENGE_TTL_SECONDS = env("WEBAUTHN_CHALLENGE_TTL_SECONDS")
WEBAUTHN_ENROLLMENT_TICKET_TTL_SECONDS = env("WEBAUTHN_ENROLLMENT_TICKET_TTL_SECONDS")
API_REQUIRE_WEBAUTHN_SESSION = env("API_REQUIRE_WEBAUTHN_SESSION")
API_ENFORCE_PASSWORD_CHANGE = env("API_ENFORCE_PASSWORD_CHANGE")
TRUST_PROXY_HEADERS = env("TRUST_PROXY_HEADERS")
USE_X_ACCEL_REDIRECT = env("USE_X_ACCEL_REDIRECT")
X_ACCEL_REDIRECT_PREFIX = env("X_ACCEL_REDIRECT_PREFIX").rstrip("/") + "/"
TEMPORARY_GRANT_MAX_HOURS = env("TEMPORARY_GRANT_MAX_HOURS")
TEMPORARY_GRANT_MAX_DOWNLOADS = env("TEMPORARY_GRANT_MAX_DOWNLOADS")
ENABLE_DJANGO_ADMIN = env("ENABLE_DJANGO_ADMIN")
ENABLE_API_DOCS = env("ENABLE_API_DOCS")
VALIDATE_UPLOAD_FILE_SIGNATURES = env("VALIDATE_UPLOAD_FILE_SIGNATURES")
SECURE_HSTS_SECONDS_VALUE = env("DJANGO_SECURE_HSTS_SECONDS")
DOCUMENT_AGENT_ENABLED = env("DOCUMENT_AGENT_ENABLED")
DOCUMENT_AGENT_PHASE5_APPROVED = env("DOCUMENT_AGENT_PHASE5_APPROVED")
DOCUMENT_AGENT_ALLOW_FAKE_PROVIDER = env("DOCUMENT_AGENT_ALLOW_FAKE_PROVIDER")
REDIS_URL = env("REDIS_URL")
DOCUMENT_AGENT_JOB_TIMEOUT_SECONDS = env("DOCUMENT_AGENT_JOB_TIMEOUT_SECONDS")
DOCUMENT_AGENT_STALE_TASK_SECONDS = env("DOCUMENT_AGENT_STALE_TASK_SECONDS")

RQ_QUEUES = {
    "document-generation": {
        "URL": REDIS_URL,
        "DEFAULT_TIMEOUT": DOCUMENT_AGENT_JOB_TIMEOUT_SECONDS,
    }
}
