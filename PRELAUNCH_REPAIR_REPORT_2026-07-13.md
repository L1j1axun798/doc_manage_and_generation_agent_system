# 上线前检查修复报告（2026-07-13）

## 1. 结论

- `CODE_AUDIT_REPORT_2026-07-10.md` 中 6 个 P0 已全部落实修复。
- 报告定义为上线前必须处理的核心 P1（P1-1、P1-2、P1-3、P1-4、P1-8、P1-9、P1-10、P1-11、P1-12、P1-13）已落实；同时完成了 P1-5、P1-6、P1-7 的权限、临时访问和上传安全修复。
- 当前代码和本地自动化基线未发现仍未关闭的 P0/核心 P1 代码阻塞项，建议先发布独立测试环境，再按第 5 节完成 Linux、TLS 和恢复演练门禁后上线生产。
- 本轮未修改已存在的历史 migration；模型检查显示无新迁移漂移。本地 MySQL 中包括 `system.0001_initial` 在内的全部迁移均已应用。

## 2. 核心修复摘要

| 范围 | 已落实结果 |
| --- | --- |
| 认证与会话 | 所有业务 API 统一校验 Django Session、用户启用状态、WebAuthn 完成标记和强制改密状态；登录增加 IP/账号双维度限速；禁用用户不能继续访问。 |
| 权限与越权 | 新版本上传必须具备更新权限；项目负责人不能转授负责人；项目成员的上传、受限下载、文件夹、删除、恢复、授权管理字段均进入后端判断；用户和授权默认硬删除接口关闭。 |
| 文件与临时访问 | 上传增加文件名、大小、扩展名和真实文件签名校验；下载统一使用鉴权后的 `X-Accel-Redirect`；临时 token 改为 URL fragment 保存、固定 POST 接口提交，并限制期限和次数；文件进入回收站立即撤销旧临时授权。 |
| 审计 | 审计 API 改为只读；Request-ID 由服务端生成；代理 IP 仅信任 Nginx 覆盖后的 `X-Real-IP`；API/审计不再返回备份绝对路径、文件存储路径或原始备份异常。 |
| 并发与一致性 | 上传、版本、移动、授权、删除和恢复等关键写路径增加事务与行锁；备份锁与永久删除互斥；陈旧锁可安全回收。 |
| 备份与恢复 | manifest 记录数据库及逐文件 SHA-256/大小；校验命令强制可信 SHA-256；恢复只允许空库和空目录；禁止覆盖式恢复；前端只展示安全摘要。 |
| 生产部署 | 增加 HTTPS 跳转、TLS Nginx、`/protected-files/ internal`、Gunicorn Unix socket、systemd、logrotate、`collectstatic`、端口收口和备份/恢复说明；生产密钥、域名和 HTTPS Origin 配置 fail-fast。 |
| 前端 | 操作按钮使用后端 capability；项目和授权表单与后端权限字段对齐；错误码/字段错误保留；临时下载、审计只读和系统备份页面已同步。 |

## 3. 实际检查结果

### 后端

| 命令/检查 | 结果 |
| --- | --- |
| `python manage.py check` | 通过，0 issue。 |
| `python manage.py check --deploy`（生产变量注入） | 命令通过；仅保留 HSTS includeSubDomains/preload 两项有意未启用的提示。 |
| `python manage.py makemigrations --check --dry-run --settings=config.settings.testing` | 通过，`No changes detected`。 |
| `pytest -q` | 通过，153 passed。 |
| `ruff check .` | 通过。 |
| `ruff format --check .` | 通过，152 files already formatted。 |
| `mypy apps common` | 通过，112 source files 无问题。 |
| `manage.py spectacular --settings=config.settings.testing --file docs/openapi.yaml --validate` | 通过，0 warning、0 error；OpenAPI 已更新。 |
| `pip check` | 通过，No broken requirements。 |
| `manage.py showmigrations --plan` | 本地 MySQL 连接成功，全部迁移为已应用。 |

### 前端

| 命令/检查 | 结果 |
| --- | --- |
| `npm run lint` | 通过。 |
| `npm run type-check` | 通过。 |
| `npm run test:unit` | 14 files、31 tests 全部通过。 |
| `npm run test:e2e` | Chromium 12 tests 全部通过。 |
| `npm run build` | 通过，生产 dist 成功生成。 |
| `npm audit --omit=dev` | 0 vulnerabilities。 |

### 备份与仓库安全

- 使用真实本地 MySQL 9.7、`mysqldump` 和 177 个业务文件生成新格式备份：记录 id=7，329,189,669 bytes；外层 SHA-256、数据库转储和逐文件哈希全部通过校验。
- 7 月 10 日的旧备份缺少逐文件哈希清单，已被新校验器正确拒绝，不能继续作为上线恢复依据；上线必须重新生成新格式生产备份。
- 恢复命令的归档校验、空目标约束和文件恢复已由自动化测试覆盖。真实临时库恢复未执行：本地 `wind_doc_user` 无 `CREATE DATABASE` 权限；未使用高权限账号绕过，且未遗留临时数据库/目录。
- 备份目录、`.env.production`、测试数据库均已忽略；仓库扫描未发现被跟踪的真实 env、备份包、数据库 dump、压缩包或超过 50 MiB 的文件，并增加 CI 仓库安全门禁。

## 4. 非阻塞提示

- `check --deploy` 的两项 HSTS 提示暂不通过强行开启 preload 处理。应先确认最终域名及其全部子域永久仅使用 HTTPS，再逐步将 HSTS 提升到长期值并评估 preload。
- Vite 构建仍提示第三方 `@vueuse/core` PURE 注释和主 chunk 约 1.01 MB；构建成功，属于 P3 性能优化，不阻塞本次安全上线。
- P1-14 已完成列表查询预取和单文件 `X-Accel-Redirect`；批量 ZIP 的 worker/内存优化可在上线后继续处理。

## 5. 生产发布前仍必须现场完成

1. 在独立测试环境填写真实 `.env.production`，使用最终 HTTPS 域名、随机密钥、MySQL 密码和 WebAuthn RP/Origin；不得使用示例占位值。
2. 在 Linux 执行 `migrate --noinput`、`collectstatic --noinput`、前端构建、`systemd-analyze verify`（如可用）和 `nginx -t`。本机 Windows 未安装 Nginx/systemd，不能声称这两项已通过。
3. 使用新格式备份恢复到管理员预先创建的空 MySQL 测试库和空文件目录，核对登录、表数据、文件数及抽样 SHA-256；演练成功后销毁测试目标。
4. 验证 80→443、Secure/HttpOnly/SameSite Cookie、CSRF、WebAuthn、`/protected-files/` 外部 404、临时下载日志不含 token，以及 5173/8000/3306 不对公网开放。
5. 完成人工冒烟：各角色权限矩阵、受限文件、授权/撤销、删除后旧链接失效、恢复、审计只读、备份校验，并确认日志不含口令、token、数据库串或磁盘绝对路径。

满足以上现场门禁后，才可将本次代码基线判定为可生产发布。
