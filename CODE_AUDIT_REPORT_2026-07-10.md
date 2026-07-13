# wind-doc-system 全面代码审查报告

审查日期：2026-07-10  
审查范围：当前工作树（含未提交改动）  
审查方式：只读代码审查、Git 状态核对、配置与部署材料核对、真实后端/前端命令验证  
本轮约束：未修改业务代码、迁移文件或配置文件；仅新增本报告

## 0. 审查边界与当前工作树

- 当前分支：`main`，最新提交：`b9f42e5 准上线版本`。
- 工作树不是干净状态，包含审计日志删除、系统备份、生产环境样例、部署说明、前端系统管理等未提交改动。本文以这些文件的当前内容为准，不把它们误认为已经合并或已部署。
- 当前存在未跟踪的 `backend/apps/system/migrations/`、`backend/.env.production.example`、`deploy/` 和系统备份实现文件；发布前必须明确哪些文件应进入版本控制。
- 当前 `backend/data/backups/` 下有两个未被 Git 忽略的备份包，大小约 329 MB/个。本报告未打开或解包这些备份，避免进一步暴露其中的数据。
- 本轮未连接生产 MySQL、未执行真实备份/恢复、未启动 Gunicorn/Nginx、未做真实 HTTPS 和公网攻击测试。涉及这些环境的结论均标记为“需部署环境确认”。

## 1. 总体结论

### 1.1 是否接近可上线

当前版本**不建议直接上线生产环境**。前端类型、Lint、单测、构建均可通过，Django 基础检查、迁移漂移检查、Ruff 和 OpenAPI 校验也通过，说明工程主体已经具备较好的模块化基础；但仍存在 6 类 P0 上线阻断风险：

1. WebAuthn 登录态只在 `/auth/me/` 检查，业务 API 接受任意合法 Django Session；Django Admin 可形成仅密码会话并直接调用业务 API。
2. “上传新版本”复用了宽松的“上传新资料”权限，普通项目查看成员或任意内部用户可替换可见文档的当前版本。
3. 项目负责人可通过修改项目 `manager` 字段绕过“仅系统管理员管理项目成员”的边界，给任意用户创建负责人权限。
4. 文档进入回收站后，既有临时下载 token 仍可继续下载。
5. 本地系统备份包未被 `.gitignore` 排除，存在数据库和业务文件被误提交的直接风险。
6. 提供的 Nginx 配置仅监听 HTTP，而生产 Cookie 强制 `Secure`；同时没有 HTTP→HTTPS 跳转，按现有材料部署既不安全也可能无法维持登录态。

### 1.2 最大风险

最大风险不是前端按钮，而是**后端安全不变量没有形成统一入口**：WebAuthn 会话要求、强制改密、文档写权限、项目成员管理、回收站状态和审计不可篡改分别散落在部分 View/Service/前端路由中。攻击者或误操作只要绕开对应前端页面、改用 Django Admin 或直接调用 API，就可能进入未覆盖路径。

### 1.3 上线建议

- 建议先修完全部 P0 和核心 P1，再部署到独立测试环境。
- 测试环境必须使用与生产一致的 MySQL、Linux 文件路径、Nginx、Gunicorn、HTTPS、`/data/documents`、`/data/exports` 和 `/data/backups`。
- 在测试环境完成权限矩阵回归、并发写测试、备份恢复演练和真实大文件下载后，再决定生产上线。

### 1.4 必须修复后才能上线

- 全部 P0。
- P1-1、P1-2、P1-3、P1-4、P1-8、P1-9、P1-10、P1-11、P1-12、P1-13。
- 后端全量测试、前端 E2E、Mypy 和既定格式检查至少要达到团队明确接受的门槛；不能把当前失败状态作为准上线基线。

## 2. 风险分级清单

## P0：必须立即修复，否则不能上线

### P0-1 WebAuthn 只保护前端登录流程，业务 API 可接受未经过 WebAuthn 的 Django Session

- 风险等级：P0
- 涉及文件和行号：
  - `backend/config/settings/base.py:144-150`
  - `backend/apps/accounts/views.py:57-65, 234-242`
  - `backend/config/urls.py:5-9`
- 问题说明：DRF 全局仅使用 `SessionAuthentication + IsAuthenticated`。WebAuthn 标记 `webauthn_verified_user_id` 只在 `/auth/me/` 中检查，其他业务 API 不检查。仓库同时公开 `/admin/`；Django Admin 默认用用户名/密码建立 Session，不会写 WebAuthn 标记。具备 `is_staff` 的账号可只用密码登录 Admin，随后用同一 Session 直接请求 `/api/v1/...`。现有后端测试大量使用 `client.force_login()` 后直接访问业务 API，也从侧面证明业务 API 没有 WebAuthn 会话约束。
- 影响范围：所有依赖登录态的业务 API；系统管理员和其他 staff 账号风险最高。密码泄露后，第二因素可能失去实际保护作用。
- 复现方式或触发条件：使用 staff 账号访问 `/admin/login/` 并只输入密码，取得 `sessionid` 后，不先调用 `/auth/me/`，直接请求 `/api/v1/documents/`、`/api/v1/users/` 等接口。
- 建议修复方案：新增统一的后端认证类或中间件，在所有业务 API 上同时校验 Django 登录态、账号有效状态和 WebAuthn Session 标记；只对白名单端点（CSRF、密码登录、WebAuthn 验证/绑定、临时下载、健康检查）豁免。生产环境应关闭或严格隔离 Admin，若保留则也必须接入同等 MFA，并限制来源 IP。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：是。前端需统一处理“需要重新本人验证”的错误码。
- 是否需要补测试：是。必须增加 Admin Session/普通 Session 无 WebAuthn 标记访问业务 API 返回 401/403，以及标准 WebAuthn Session 可访问的回归测试。

### P0-2 普通可见用户可上传新版本并替换当前版本

- 风险等级：P0
- 涉及文件和行号：
  - `backend/apps/documents/views.py:122-133`
  - `backend/apps/documents/services.py:108-155, 456-465`
  - `backend/apps/documents/permissions.py:9-20, 41-51`
  - `fronted/src/modules/documents/components/DocumentTable.vue:91-95`
- 问题说明：`versions` 接口获取“可见文档”后，`create_document_version()` 仅调用 `_ensure_upload_allowed()`。该权限允许任意项目成员上传项目资料，并允许任意已登录非临时用户上传公共资料；它没有调用 `can_update_document()`。因此查看者成员可替换项目文档当前版本，任意内部用户可替换公共文档当前版本。前端还对所有非归档行显示“新版本”按钮。
- 影响范围：公司资料、人员/设备/车辆资质、项目资料的文件完整性和版本可信度；属于直接写越权。
- 复现方式或触发条件：以 `ProjectMember.Role.VIEWER` 且 `can_upload=False` 的项目成员登录，对可见文档调用 `POST /api/v1/documents/{id}/versions/`；公共资料可由任意普通内部用户尝试同一路径。
- 建议修复方案：新增版本必须调用 `can_update_document()` 或单独的 `can_create_document_version()`，并在锁定文档后再次检查权限、删除状态和项目归档状态。前端由后端返回 `can_create_version` 能力位后再显示按钮。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：是。
- 是否需要补测试：是。至少覆盖管理员、显式更新授权、项目负责人、普通成员、查看者、公共资料普通用户、已归档项目和已删除文档。

### P0-3 项目负责人可绕过成员管理边界给其他用户授予负责人权限

- 风险等级：P0
- 涉及文件和行号：
  - `backend/apps/projects/permissions.py:9-17`
  - `backend/apps/projects/serializers.py:11-41`
  - `backend/apps/projects/views.py:50-59`
  - `backend/apps/projects/services.py:42-60, 248-256`
- 问题说明：成员增删改明确限制为系统管理员，但项目负责人可更新项目；`ProjectSerializer.manager` 可写，`update_project()` 在 manager 变化时直接 `update_or_create` 一个带负责人默认权限的 `ProjectMember`。这使项目负责人通过 PATCH 项目即可绕过成员管理 API 的系统管理员限制。原负责人关系也不会被移除或降级，导致 `Project.manager` 与多个 MANAGER 成员长期不一致。
- 影响范围：项目成员权限、目录管理、删除/恢复以及后续若启用 `can_manage_permission` 后的授权边界。
- 复现方式或触发条件：项目负责人对自己的项目发送 `PATCH /api/v1/projects/{id}/ {"manager": 其他用户ID}`，观察新用户获得 MANAGER 成员及默认权限。
- 建议修复方案：项目负责人更新项目时禁止修改 `manager`；负责人变更建立系统管理员专用 Service，在同一事务中锁项目与成员、校验目标用户、明确转移/保留策略，并审计前后关系。检查现有数据中 manager FK 与 MANAGER 成员不一致的记录。
- 是否需要数据库迁移：通常否；需要一次数据审计/修复。若改为数据库约束或单一负责人关系，可能需要迁移。
- 是否需要前后端联动：是。非管理员项目表单不得提交 manager。
- 是否需要补测试：是。覆盖负责人自助改 manager 被拒、管理员转移成功、旧负责人权限处理和并发转移。

### P0-4 文档进入回收站后，旧临时链接仍可下载

- 风险等级：P0
- 涉及文件和行号：
  - `backend/apps/documents/models.py:51-59`
  - `backend/apps/access/temporary_services.py:98-168`
  - `backend/apps/access/models.py:115-125`
- 问题说明：临时授权有效性只检查撤销、过期和次数；消费 token 时未检查 `document_version.document.deleted_at`。软删除不会撤销临时授权，因此删除后的文件仍能通过旧链接访问。
- 影响范围：回收站语义、撤回敏感文件、外部临时访问。
- 复现方式或触发条件：创建临时链接，软删除文档，再匿名请求 `/api/v1/temporary-access/{token}/download/`。
- 建议修复方案：消费 token 时在同一锁定事务中检查文档未删除；软删除时可选择批量撤销全部活动临时授权并审计。恢复文档后是否恢复旧链接必须明确，默认不应自动恢复。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否，错误提示可联动优化。
- 是否需要补测试：是。覆盖删除前成功、删除后拒绝、恢复后旧 token 仍拒绝、永久删除级联。

### P0-5 系统备份包未被 Git 忽略，当前已作为未跟踪文件出现

- 风险等级：P0
- 涉及文件和行号：
  - `.gitignore:35-39`
  - `backend/.env.example:18-26`
  - 当前路径：`backend/data/backups/wind-doc-system-backup-20260710-094714-5.tar.gz`、`...094935-6.tar.gz`
- 问题说明：`.gitignore` 只忽略 `data/files` 和 `data/temporary`，没有忽略 `data/backups`。当前两个约 329 MB 的备份包已经出现在 `git status` 的 `??` 列表。备份设计包含 MySQL dump 与全部业务文件，一次 `git add .` 就可能造成严重数据泄露和仓库膨胀。
- 影响范围：数据库全量数据、业务文件、个人信息、资质材料及 Git 历史。
- 复现方式或触发条件：在开发配置执行 `create_system_backup` 后运行 `git status --short` 或 `git add . --dry-run`。
- 建议修复方案：立即忽略 `backend/data/backups/*`，只保留必要 `.gitkeep`；在提交钩子/CI 增加大文件和压缩包/数据库 dump 拦截；确认这些包从未进入任何分支或远端历史。如已进入历史，按泄露事件处理而不是只做普通删除。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否。
- 是否需要补测试：建议增加仓库级 secret/large-file 检查。

### P0-6 当前生产入口只有 HTTP，但生产 Cookie 强制 Secure，且没有 HTTPS 跳转

- 风险等级：P0
- 涉及文件和行号：
  - `backend/config/settings/production.py:3-9`
  - `deploy/nginx/wind-doc-system.conf:1-23`
  - `deploy.md:49-64`
- 问题说明：生产设置正确启用了 `SESSION_COOKIE_SECURE` 和 `CSRF_COOKIE_SECURE`，但提供的 Nginx 配置只 `listen 80`，没有 443、证书、HTTP→HTTPS 重定向；`check --deploy` 也实际报告 `security.W008` 和 `security.W004`。按现有配置部署时，浏览器不会在 HTTP 上正常使用 Secure Session Cookie，同时口令、WebAuthn ceremony 和文件传输也不满足生产安全要求。
- 影响范围：生产登录、CSRF、所有业务数据传输和 WebAuthn。
- 复现方式或触发条件：按 `deploy.md` 和当前 Nginx 文件原样部署后，通过 `http://documents.example.com` 登录。
- 建议修复方案：继续沿用 Nginx + Gunicorn 路线，补齐 443 TLS server、80→443 301 跳转、证书更新流程；确认反向代理只在可信链路设置 `X-Forwarded-Proto`。在 HTTPS 全站稳定后再设置合适 HSTS 值并分阶段启用。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：主要是部署联动；前端 API 已使用相对路径，无需改成绝对域名。
- 是否需要补测试：需要部署冒烟测试，验证 Secure Cookie、CSRF、WebAuthn origin、HTTP 跳转和大文件下载。

## P1：上线前强烈建议修复

### P1-1 首次/重置密码强制改密只由前端路由守卫执行

- 风险等级：P1
- 涉及文件和行号：`fronted/src/core/router/guards.ts:34-44`，`backend/config/settings/base.py:144-150`，`backend/apps/accounts/views.py:245-278`
- 问题说明：`must_change_password` 只在前端跳转 `/change-password`，后端业务 API 没有统一拒绝。用户完成登录后可直接调用 API，绕过改密要求。
- 影响范围：管理员重置密码、首次登录账号的安全策略。
- 复现方式或触发条件：用 `must_change_password=True` 用户完成登录后直接请求任一业务 API。
- 建议修复方案：在统一认证/权限层拒绝此类账号访问除 `/auth/me/`、改密、退出和必要 WebAuthn 端点外的业务 API，并返回稳定错误码。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：是。
- 是否需要补测试：是。

### P1-2 用户与文档授权仍暴露默认硬删除接口

- 风险等级：P1
- 涉及文件和行号：`backend/apps/accounts/views.py:281-340`，`backend/apps/access/views.py:14-61`
- 问题说明：两个类仍是 `ModelViewSet` 且未禁用 DELETE。用户硬删除会绕过 `disable_user()` 并触发多处 CASCADE/SET_NULL；授权硬删除会绕过 `revoke_document_grant()` 和审计。前端不显示按钮并不能构成安全边界。
- 影响范围：用户、项目成员、授权、WebAuthn 凭据、通知、定位、审计关联和追责。
- 复现方式或触发条件：系统管理员直接发送 `DELETE /api/v1/users/{id}/` 或 `DELETE /api/v1/document-grants/{id}/`。
- 建议修复方案：从允许方法中移除 DELETE；用户只允许停用，授权只允许撤销。若确需永久删除，设计独立受控流程、依赖检查、双重确认和审计。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否。
- 是否需要补测试：是，明确断言 DELETE 返回 405。

### P1-3 审计日志支持单条和批量永久删除，无法形成不可抵赖证据

- 风险等级：P1
- 涉及文件和行号：`backend/apps/audit/views.py:18-50`，`backend/apps/audit/services.py:41-82`，`fronted/src/modules/audit/pages/AuditLogPage.vue:101-161, 176-181, 242-249`
- 问题说明：系统管理员可删除任意审计日志，删除后仅再写一条删除记录，而该记录本身也可再次删除。普通用户确实无法读取，但高权限账号可清除证据，不满足审计日志的防篡改目标。
- 影响范围：登录、下载、授权、删除、备份等关键操作的追责。
- 复现方式或触发条件：管理员批量删除目标日志，再删除生成的 `audit_log.bulk_delete` 日志。
- 建议修复方案：业务 API 改为只读；如有合规保留期限，使用只允许后台计划任务执行的归档/分区清理，写入独立不可变更介质或至少建立数据库权限隔离和链式摘要。前端删除入口应移除。
- 是否需要数据库迁移：否；若增加归档/哈希链字段则需要迁移。
- 是否需要前后端联动：是。
- 是否需要补测试：是。

### P1-4 Django Admin 可绕过 Service、权限校验和业务审计直接改数据

- 风险等级：P1
- 涉及文件和行号：`backend/apps/documents/admin.py:6-24`，`backend/apps/access/admin.py:6-34`，以及 projects/folders 等默认 Admin 注册
- 问题说明：除 AuditLog 外，多数 Admin 页面允许直接新增、修改、删除模型，绕过项目归档、文件夹合法性、授权撤销、文件/数据库一致性和业务审计。DocumentVersion 的 `storage_path`、current_version 关系也可能被直接改坏。
- 影响范围：几乎所有核心数据和权限边界。
- 复现方式或触发条件：授予 staff 对应模型权限后，在 `/admin/` 直接编辑 Document、DocumentGrant、TemporaryAccessGrant 或 Project。
- 建议修复方案：生产环境默认禁用或 IP 隔离 Admin；核心模型 Admin 改只读，禁止 add/change/delete。确需操作的管理动作调用同一 Service，并记录审计，不允许直接 ModelForm 保存。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否。
- 是否需要补测试：是，增加 Admin permission 测试。

### P1-5 `access_level` 与多项项目权限字段未参与实际授权，前后端角色契约不一致

- 风险等级：P1
- 涉及文件和行号：
  - `backend/apps/documents/models.py:5-31`
  - `backend/apps/documents/permissions.py:23-89`
  - `backend/apps/projects/models.py:74-80`
  - `backend/apps/projects/serializers.py:44-68`
  - `backend/apps/access/permissions.py:6-7`
  - `fronted/src/core/router/index.ts:88-97`
- 问题说明：Document 的 `INTERNAL/RESTRICTED` 没有进入序列化或权限判断；`can_download_restricted`、`can_manage_permission`、`can_manage` 等字段基本未生效。前端允许 project_manager 进入授权管理，后端又只允许系统管理员，形成空页面/403。字段名会让管理员误以为权限已经生效。
- 影响范围：受限资料、项目负责人/资料整理员的功能边界、授权管理。
- 复现方式或触发条件：将文档设为 restricted 后比较普通项目成员可见性；给成员 `can_manage_permission=True` 后访问授权 API；用 project_manager 打开授权管理页面。
- 建议修复方案：先由业务负责人确认唯一权限矩阵，再删除废弃字段或真正接入 selector/permission/service/serializer/API capability。不要保留“看起来可配置但实际无效”的权限。
- 是否需要数据库迁移：取决于决策；删除/重构字段需要迁移，接入现有字段可不迁移。
- 是否需要前后端联动：是。
- 是否需要补测试：是，按角色×资源范围×动作建立矩阵测试。

### P1-6 临时下载使用 URL 中的 GET token，可能被日志/扫描器消耗，且期限和次数无上限

- 风险等级：P1
- 涉及文件和行号：`backend/apps/access/temporary_views.py:84-98`，`backend/apps/access/temporary_serializers.py:63-68`，`fronted/src/modules/access/pages/TemporaryDownloadPage.vue:9-28`，`deploy/nginx/wind-doc-system.conf:16-23`
- 问题说明：token 出现在前端路由、API URL、Nginx access log 和 Referer 中；GET 请求会立即增加使用次数。安全扫描器、预取或误点可能消耗次数。创建端没有最大有效期和最大下载次数上限。
- 影响范围：外部临时访问的保密性和可用性。
- 复现方式或触发条件：查看 Nginx 访问日志中的 `/temporary-access/{token}/download/`；用链接扫描器请求一次后再由真实用户下载。
- 建议修复方案：至少为敏感路径关闭/脱敏 access log；设置最大期限和最大次数；下载页先用 token 换取短时一次性凭据，再 POST 消费，避免页面资源 Referer 携带原 token。明确计数是“请求次数”还是“成功传输次数”。
- 是否需要数据库迁移：通常否。
- 是否需要前后端联动：是。
- 是否需要补测试：是。

### P1-7 上传只校验扩展名和声明大小，未验证真实格式；跨平台文件名规范化不足

- 风险等级：P1
- 涉及文件和行号：`backend/common/validators.py:7-42`，`backend/apps/documents/services.py:53-75, 582-599`，`backend/apps/documents/services.py:566-578`
- 问题说明：可把任意内容伪装成 `.jpg/.pdf` 上传；`content_type` 完全采用客户端声明。生产 Linux 上 `PurePath` 不会把反斜杠当分隔符，恶意 multipart 文件名可能以 `..\name.pdf` 形式进入元数据和 ZIP arcname。存储路径本身使用随机摘要目录，当前未发现直接磁盘路径穿越，但恶意文件传播和 ZIP 文件名风险仍在。
- 影响范围：公司内部恶意文件传播、下载响应类型、批量 ZIP 安全。
- 复现方式或触发条件：上传内容为脚本/可执行数据但文件名为 `report.pdf`；在 Linux 发送带反斜杠/控制字符的 multipart filename。
- 建议修复方案：扩展名、MIME 嗅探、文件签名三者联合校验；图片用 Pillow 解码校验，Office/PDF 做结构检查或病毒扫描；服务端统一移除路径分隔符、控制字符、CR/LF 和保留名；响应默认 `application/octet-stream` + attachment。
- 是否需要数据库迁移：否；若新增扫描状态字段则需要。
- 是否需要前后端联动：可选，前端显示扫描中/拒绝原因。
- 是否需要补测试：是。

### P1-8 审计来源可被请求头伪造，超长 Request-ID 可破坏审计写入；审计数据含存储路径

- 风险等级：P1
- 涉及文件和行号：`backend/common/middleware.py:7-18`，`backend/apps/audit/models.py:23-28`，`backend/apps/audit/services.py:102-108`，`deploy/nginx/wind-doc-system.conf:19-21`，`backend/apps/documents/services.py:617-625`
- 问题说明：Request-ID 直接信任客户端且未限制到模型的 64 字符；审计 IP 取 X-Forwarded-For 第一个值，而 Nginx 使用 `$proxy_add_x_forwarded_for`，客户端可伪造首段。严格 MySQL 模式下超长值还可能使审计插入失败并连带业务事务失败。版本快照把 `storage_path` 写入 AuditLog，系统备份 API也返回服务器绝对路径和原始错误信息。
- 影响范围：审计可信度、关键写操作可用性、内部路径和部署信息泄露。
- 复现方式或触发条件：携带超长 `X-Request-ID` 或伪造 `X-Forwarded-For` 执行上传/授权；查看审计详情的 version snapshot。
- 建议修复方案：服务端生成规范 Request-ID，或只接受固定字符集和长度；Nginx 覆盖而不是追加不可信 XFF，并在 Django 只信任固定代理；审计 snapshot 去除 storage_path、token、数据库路径和原始敏感 stderr。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否。
- 是否需要补测试：是。

### P1-9 关键唯一规则主要靠“先查再写”，并发下可产生重复或不一致

- 风险等级：P1
- 涉及文件和行号：`backend/apps/folders/models.py:39-45`，`backend/apps/folders/services.py:179-195`，`backend/apps/documents/models.py:61-68`，`backend/apps/documents/services.py:510-533`，`backend/apps/access/models.py:46-52`，`backend/apps/access/serializers.py:64-78`
- 问题说明：同级文件夹名、同目录文档名/内容、活动授权唯一性都用 `exists()` 后创建，没有数据库唯一约束或稳定锁。并发请求可能同时通过检查。文档创建的重复检查还在数据库事务外；项目删除与并发上传也没有共享项目锁。
- 影响范围：目录树、文件列表、授权合并语义、项目删除后的磁盘孤儿文件。
- 复现方式或触发条件：并发提交两个同名文件/文件夹/授权，或空项目删除与上传同时发生。
- 建议修复方案：能表达的规则使用数据库约束；MySQL NULL 语义下可用规范化 parent key/active key 或事务锁实现。关键写路径锁 Folder/Project/Document，并捕获 IntegrityError 转业务冲突。为文件元数据与磁盘写入增加可重试/补偿机制。
- 是否需要数据库迁移：是，新增约束/辅助字段/索引时需要新 migration，不能改历史 migration。
- 是否需要前后端联动：否，建议统一返回 409。
- 是否需要补测试：是，必须在 MySQL 上做并发测试。

### P1-10 备份并非数据库与文件的一致时间点，校验和恢复流程也不够可靠

- 风险等级：P1
- 涉及文件和行号：
  - `backend/apps/system/services.py:97-128, 229-277, 375-426`
  - `backend/apps/system/management/commands/restore_system_backup.py:25-58, 105-153`
- 问题说明：先执行 MySQL single-transaction dump，再扫描并打包文件目录；期间删除/永久删除可让 dump 引用的文件不再进入包。`verify_backup_archive()` 默认只检查结构并计算当前包 hash，不与数据库记录的预期 SHA 自动绑定，也不核验 manifest 内 database.sql hash/文件统计。进程崩溃可能遗留 `.backup.lock` 永久阻塞后续任务。生产覆盖恢复只是把 SQL 导入非空库并叠加文件目录，不是原子切换，失败会留下混合状态。
- 影响范围：灾难恢复成功率，是生产可用性的核心风险。
- 复现方式或触发条件：备份期间永久删除文件；杀死备份进程后重跑；对可正常解压的包修改 manifest/database 内容后不传 `--sha256` 校验；覆盖恢复中途失败。
- 建议修复方案：建立应用级备份锁/短维护窗口，使文件删除与备份互斥；生成精确文件清单并逐项 hash；verify 自动读取 `SystemBackupRun.sha256` 或必须提供可信期望值；锁文件包含 PID/时间并支持安全判定过期；恢复先到空库/新目录，完整验证后再切换，禁止直接叠加生产目录。
- 是否需要数据库迁移：通常否；若记录文件清单/恢复任务则需要。
- 是否需要前后端联动：前端只展示安全摘要，不展示服务器绝对路径和原始异常。
- 是否需要补测试：是；需 Linux + MySQL + 真实 mysqldump/mysql 的集成和恢复演练。

### P1-11 生产部署材料缺少 Gunicorn/systemd、collectstatic、内部下载和网络收口闭环

- 风险等级：P1
- 涉及文件和行号：`deploy.md:39-64`，`deploy/nginx/wind-doc-system.conf:16-34`，`backend/config/settings/base.py:133-134`
- 问题说明：已有 `/data/documents`、`/data/exports`、备份和 Nginx 私有目录拒绝说明，这是正确方向；但没有 Gunicorn 启动参数、systemd unit/用户/工作目录/超时、`collectstatic`、`createsuperuser`、日志目录权限、端口/安全组收口说明，也没有 `/protected-files/ internal` 下载方案。当前下载由 Django/Gunicorn 直接流式传输，Nginx 还关闭 proxy buffering。
- 影响范围：部署可重复性、大文件下载、进程守护、静态资源、运维安全。
- 复现方式或触发条件：仅根据现有 deploy.md 在空 ECS 上部署，无法得到完整、可守护、HTTPS 可用的服务。
- 建议修复方案：补齐 Nginx + Gunicorn + systemd 单机模板；Gunicorn 仅绑定 `127.0.0.1` 或 Unix socket；3306 仅本机；安全组只开放 80/443/受限 SSH。鉴权后返回受控 `X-Accel-Redirect` 到 `internal` location，外部直接访问必须 404。补 `collectstatic`、日志轮转与权限说明。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否。
- 是否需要补测试：需要部署脚本/冒烟测试。

### P1-12 当前自动化验证不是全绿，不能作为准上线基线

- 风险等级：P1
- 涉及文件和行号：`backend/apps/access/tests/test_document_grant_api.py:25-38, 263`，`backend/apps/documents/tests/test_document_batch_download_api.py:28-40, 64`，`fronted/e2e/app.spec.ts:291, 477`
- 问题说明：后端 141 项中 2 项失败，原因是新“同目录同名/同内容禁止”规则与旧测试数据冲突；E2E 12 项中 2 项失败，分别找不到“人员名单”和“详情”。Mypy 23 个错误，Ruff format check 12 个文件不合规。测试失败目前主要体现测试/契约漂移，但在未校正前无法判断相关流程是否被可靠保护。
- 影响范围：授权改绑、批量下载、资料中心、授权管理、类型安全和交付质量。
- 复现方式或触发条件：见第 6 节实际命令。
- 建议修复方案：先确认重复文件业务规则，再调整不再成立的测试数据而不是放宽规则；修复 E2E 落地状态；把迁移排除出格式命令或只格式化未应用业务代码，禁止为了通过检查重写历史迁移；逐步清零 Mypy。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：是，E2E 与 API 契约需同步。
- 是否需要补测试：是。

### P1-13 登录没有启用速率限制/锁定，尽管依赖中已包含 django-axes

- 风险等级：P1
- 涉及文件和行号：`backend/requirements/base.txt:9`，`backend/config/settings/base.py:42-62, 144-160`，`backend/apps/accounts/views.py:78-119`
- 问题说明：没有 `axes` app/backend/middleware，也没有 DRF throttle。攻击者可持续尝试用户名密码，并大量创建 WebAuthn challenge/audit 记录。停用账号与不存在账号返回不同状态/消息，也可辅助账号枚举。
- 影响范围：认证入口、数据库和审计容量。
- 复现方式或触发条件：对 `/api/v1/auth/login/` 连续提交错误密码，无 429/锁定。
- 建议修复方案：正确配置 django-axes 或等效服务端限速，按用户名+可信 IP 组合限流，避免永久锁死；统一外部错误消息，内部审计保留具体原因；为 challenge 增加清理任务。
- 是否需要数据库迁移：django-axes 可能需要其自带迁移。
- 是否需要前后端联动：是，前端处理 429/冷却时间。
- 是否需要补测试：是。

### P1-14 列表存在 N+1，下载路径会占用大量 Web worker/浏览器内存

- 风险等级：P1
- 涉及文件和行号：`backend/apps/accounts/serializers.py:10-36`，`backend/apps/documents/serializers.py:30-66`，`backend/apps/documents/services.py:402-453`，`fronted/src/modules/documents/api/documents.api.ts:83-90`
- 问题说明：用户列表每行查询 WebAuthn exists+count；文档列表每行查询 `can_download` grant。批量下载在 Web 进程压缩最多 500 MB，单文件前端 Axios Blob 也会把完整文件缓存在浏览器内存。大文件会长时间占用 Gunicorn worker。
- 影响范围：用户管理、资料列表、并发下载和服务器内存。
- 复现方式或触发条件：分页 20 条非管理员文档/用户并记录 SQL；并发下载多个 200 MB 文件或生成 500 MB ZIP。
- 建议修复方案：QuerySet 注解/Prefetch 一次计算能力与凭据统计；下载采用鉴权后 X-Accel-Redirect；批量 ZIP 改后台任务或严格降低上限并控制 worker；前端避免不必要的全量 Blob 缓存。
- 是否需要数据库迁移：通常否。
- 是否需要前后端联动：X-Accel 和异步 ZIP 需要联动。
- 是否需要补测试：建议加入 query-count 和大文件压测。

## P2：上线后短期内修复

### P2-1 前端显示的文档操作按钮没有使用后端能力位，永久删除也没有页面入口

- 风险等级：P2
- 涉及文件和行号：`backend/apps/documents/serializers.py:30-66`，`fronted/src/modules/documents/documents.types.ts:26-44`，`fronted/src/modules/documents/components/DocumentTable.vue:72-96`
- 问题说明：API 仅返回 `can_download`，前端对所有非归档文档显示修改、移动、新版本、删除，对回收站所有条目显示恢复；无权限用户频繁收到 403。后端已有 permanent-delete API，但前端无入口。
- 影响范围：资料中心 UX、权限认知、回收站完整性。
- 复现方式或触发条件：普通查看者浏览资料表/回收站。
- 建议修复方案：后端统一返回 `can_update/can_move/can_create_version/can_delete/can_restore/can_permanently_delete`，前端只做显示收敛；真实安全仍由后端执行。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：是。
- 是否需要补测试：是。

### P2-2 前端字段错误解析与后端标准错误结构不匹配

- 风险等级：P2
- 涉及文件和行号：`backend/common/exceptions.py:16-24`，`fronted/src/core/http/error-normalizer.ts:56-92`
- 问题说明：后端字段错误位于 `errors`，前端却遍历顶层字段，导致表单拿不到结构化错误；后端 `_extract_message` 对字段字典又可能显示 Python 字典字符串。
- 影响范围：用户/授权/文档表单错误提示。
- 复现方式或触发条件：提交重复用户名、无效授权或字段校验错误。
- 建议修复方案：前端优先展开 `data.errors`；后端给首个字段错误生成稳定人类消息，并保留错误码。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：是。
- 是否需要补测试：是。

### P2-3 授权管理搜索参数被前端发送，但后端没有 search_fields

- 风险等级：P2
- 涉及文件和行号：`fronted/src/modules/access/pages/AccessManagementPage.vue:28-58`，`backend/apps/access/views.py:14-25`，`backend/apps/access/temporary_views.py:26-44`
- 问题说明：页面提交 `search`，两个 ViewSet 没定义 `search_fields`，默认 SearchFilter 不会产生预期检索。
- 影响范围：授权记录较多时无法有效查找。
- 复现方式或触发条件：输入授权对象/用户/文件名搜索，结果不变化。
- 建议修复方案：增加受控 search_fields 或专用 selector，注意用户手机号等敏感字段只对管理员可见。
- 是否需要数据库迁移：否；规模较大时索引优化可能需要。
- 是否需要前后端联动：否。
- 是否需要补测试：是。

### P2-4 文件夹 tree 的 GET 请求会写数据库

- 风险等级：P2
- 涉及文件和行号：`backend/apps/folders/views.py:51-67`，`backend/apps/projects/services.py:259-274`
- 问题说明：读取 tree 时可能 `update_or_create` 项目标准目录。GET 不需要 CSRF，缓存/预取/重试可能触发写入，且该写入没有业务审计。
- 影响范围：HTTP 语义、审计和并发目录创建。
- 复现方式或触发条件：成员首次 GET 某活动项目 tree。
- 建议修复方案：项目创建/迁移/显式修复命令中创建标准目录；GET 只读。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否。
- 是否需要补测试：是，断言 GET 不改变数据库。

### P2-5 临时文件、WebAuthn challenge/ticket、过期授权与备份元数据缺少完整清理闭环

- 风险等级：P2
- 涉及文件和行号：`backend/config/settings/base.py:190-208`，`backend/apps/accounts/models.py:93-165`，`backend/apps/system/services.py:265-277`
- 问题说明：临时导出目录没有定期清理实现；过期 challenge/ticket/grant 只在查询时失效但不删除；备份清理删文件后仍保留 success 路径和 offsite_available 语义，UI可能显示已校验但文件已不存在。
- 影响范围：磁盘/数据库增长和运维误判。
- 复现方式或触发条件：长期运行、频繁登录/定位/临时授权/备份。
- 建议修复方案：增加受审计的定时清理命令；备份记录标记 expired/deleted 或清空路径；为临时导出使用唯一目录和 finally/on_commit 清理。
- 是否需要数据库迁移：备份状态扩展可能需要。
- 是否需要前后端联动：备份状态需要。
- 是否需要补测试：是。

### P2-6 数据模型的更新时间/操作者字段和删除策略不完全一致

- 风险等级：P2
- 涉及文件和行号：`backend/apps/accounts/models.py:9-29`，`backend/apps/projects/models.py:5-96`，`backend/apps/locations/models.py:5-46`，`backend/apps/notifications/models.py:5-41`
- 问题说明：User 只有 created_at、没有 updated_at/updated_by；Project/Document/Folder 有 updated_at 但无 updated_by；ProjectMember/LocationReport/Notification 的生命周期字段不一致。用户删除对位置、通知、成员、授权使用 CASCADE，和系统整体偏软删除/保留审计的方向冲突。
- 影响范围：变更追踪、数据保留、用户离职处理。
- 复现方式或触发条件：用户硬删除或调查某条数据最近由谁修改。
- 建议修复方案：先定义保留政策，再补必要操作者字段；用户只停用，重要历史关系优先 SET_NULL/快照而不是 CASCADE。
- 是否需要数据库迁移：是。
- 是否需要前后端联动：通常否。
- 是否需要补测试：是，特别是用户停用/删除数据保留。

### P2-7 登录和会话前端还有状态与文案问题

- 风险等级：P2
- 涉及文件和行号：`fronted/src/modules/auth/stores/auth.store.ts:61-73`，`fronted/src/modules/auth/pages/LoginPage.vue:61-79`，`fronted/src/core/router/guards.ts:64-72`，`fronted/src/modules/auth/services/webauthn.ts:63-67`
- 问题说明：登录失败后 store 可能停留在 loading；登录页写“用户名/手机号”，后端只按 username authenticate；访问 login 时 initializeSession 的服务器异常没有与主守卫同样捕获；生产 RP 错误仍提示 localhost 地址。全局 401/403 也不会自动清理过期会话并回登录。
- 影响范围：登录失败、会话过期和生产 WebAuthn 排障体验。
- 复现方式或触发条件：错误密码、后端 500、手机号登录、生产 RP 配置错误、会话中途过期。
- 建议修复方案：统一状态机和错误处理；文案与真实登录标识一致；生产错误用当前配置/通用提示；全局认证失效事件安全跳转登录。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：手机号登录若要支持则需要。
- 是否需要补测试：是。

### P2-8 API schema/docs 和 health 在生产默认公开

- 风险等级：P2
- 涉及文件和行号：`backend/config/urls.py:5-9`，`backend/apps/system/views.py:17-30`
- 问题说明：匿名用户可获取 API 结构、服务名和 debug 状态。不是直接越权，但会降低攻击成本。
- 影响范围：接口枚举和部署信息暴露。
- 复现方式或触发条件：匿名访问 `/api/schema/`、`/api/docs/`、`/api/v1/health/`。
- 建议修复方案：生产关闭 Swagger/schema 或仅管理员/内网访问；health 只返回最小状态，不返回 debug。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否。
- 是否需要补测试：是，按环境断言。

### P2-9 测试数据库使用 SQLite，关键 MySQL 行为和真实备份工具未覆盖

- 风险等级：P2
- 涉及文件和行号：`backend/config/settings/testing.py:5-10`，`backend/pytest.ini:1-5`，`backend/apps/system/tests/test_system_backup.py`
- 问题说明：测试全部基于 SQLite；MySQL 的字符集、NULL 唯一语义、锁、事务隔离、外键和并发行为没有验证。备份测试使用回调/模拟，未证明 ECS 上 mysqldump/mysql 命令和恢复可用。
- 影响范围：并发一致性、迁移、备份恢复。
- 复现方式或触发条件：当前 `pytest` 输出 settings 为 `config.settings.testing` 且数据库为 SQLite。
- 建议修复方案：保留快速 SQLite 单测，同时在 CI/测试环境增加 MySQL 集成测试和每月真实恢复演练。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否。
- 是否需要补测试：是。

### P2-10 生产秘密和服务器路径缺少 fail-fast/最小披露

- 风险等级：P2
- 涉及文件和行号：`backend/config/settings/base.py:9-40`，`backend/.env.production.example:1-9`，`backend/apps/system/serializers.py:11-31`，`fronted/src/modules/system/pages/SystemManagementPage.vue:301-317`
- 问题说明：production.py 会强制 DEBUG=False，这是正向项；但 SECRET_KEY 仍有不安全默认值，未在生产启动时拒绝占位值。备份 API/页面直接显示服务器绝对路径和原始错误。
- 影响范围：误配置和内部路径披露（当前仅系统管理员可见）。
- 复现方式或触发条件：只配置 MySQL 而遗漏真实 SECRET_KEY 启动；打开系统管理备份页。
- 建议修复方案：生产设置对 secret、host、DB 密码占位符、数据目录执行 fail-fast；API只返回文件名、是否存在、hash、大小和安全错误码。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：是。
- 是否需要补测试：是。

## P3：优化建议

### P3-1 大文件模块职责过重

- 风险等级：P3
- 涉及文件和行号：`backend/apps/documents/services.py:1-626`，`backend/apps/accounts/views.py:1-340`，`backend/apps/accounts/webauthn_services.py:1-463`，`backend/apps/system/services.py:1-488`，`fronted/src/modules/documents/components/DocumentExplorer.vue:1-864`
- 问题说明：虽然已有 services/selectors/permissions 分层，但上述模块同时处理多个独立流程，审查和回归成本较高。
- 影响范围：维护性和误改风险。
- 复现方式或触发条件：任一文件变化需要理解多个不相干流程。
- 建议修复方案：在 P0/P1 稳定后按“版本、下载、回收站、备份/恢复、WebAuthn purpose、公共目录 UI”拆分，不做上线前大重构。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否。
- 是否需要补测试：重构前先补行为测试。

### P3-2 前端主 chunk 超过 1 MB

- 风险等级：P3
- 涉及文件和行号：`fronted/vite.config.ts:1-26`，本轮 build 输出
- 问题说明：构建成功，但主 `index` chunk 约 1,013.86 kB（gzip 328.78 kB），构建器发出 >500 kB 警告。
- 影响范围：首次加载速度，内网环境影响有限。
- 复现方式或触发条件：`npm run build`。
- 建议修复方案：按 Element Plus/地图/大型模块拆包，保持路由懒加载；上线阻断项完成后再优化。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否。
- 是否需要补测试：否，需性能基线。

### P3-3 开发种子命令含固定密码和生产强制开关

- 风险等级：P3
- 涉及文件和行号：`backend/apps/system/management/commands/seed_dev_data.py:23, 32-40, 178-210`
- 问题说明：默认受 DEBUG 保护，但 `--force` 可在非 DEBUG 执行，并会把固定密码写给多个演示账号。
- 影响范围：运维误操作。
- 复现方式或触发条件：生产误执行 `seed_dev_data --force`。
- 建议修复方案：生产包禁用该命令或增加不可轻易绕过的环境确认；演示密码改为随机并强制改密。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：否。
- 是否需要补测试：已有 DEBUG 防护测试可继续加强。

### P3-4 Cookie/Session 策略应显式文档化

- 风险等级：P3
- 涉及文件和行号：`backend/config/settings/base.py:139-143`，`backend/config/settings/production.py:5-9`
- 问题说明：HttpOnly、Secure 和代理头设置总体正确，SameSite 依赖 Django 默认值，Session 默认寿命也未明确。后续升级可能让行为不够直观。
- 影响范围：安全配置可维护性。
- 复现方式或触发条件：框架升级或跨域部署方式变化。
- 建议修复方案：显式配置并记录 `SESSION_COOKIE_SAMESITE=Lax`、CSRF SameSite、Session age、浏览器关闭策略；生产坚持同源 `/api`，不为方便而放宽 CORS/CSRF。
- 是否需要数据库迁移：否。
- 是否需要前后端联动：可能需要登录过期提示。
- 是否需要补测试：建议 Cookie 属性集成测试。

## 3. 安全专项结论

### 3.1 认证是否可靠

- 密码校验、Django password validator、WebAuthn challenge 随机性、哈希存储、过期、单次消费、origin/RP ID、签名计数和用户验证要求总体实现较好。
- 禁用用户由 Django backend 拒绝后续认证，修改本人密码使用 `update_session_auth_hash()`，这些是正向项。
- 但认证整体目前**不可靠**，核心原因是 WebAuthn Session 不在所有业务 API 统一执行（P0-1），强制改密也只在前端（P1-1），且没有登录限速（P1-13）。
- 未发现公开自助注册。匿名 WebAuthn 绑定端点依赖高熵、过期、单次 ticket，方向正确。

### 3.2 权限是否可靠

- 项目/文件/授权 selector 大多先收窄 QuerySet，IDOR 防护基础较好；对象不存在与无权访问多返回 404。
- 用户、审计、系统备份和全部人员位置接口均由后端管理员权限控制，不依赖前端菜单。
- 但新版本上传和 manager 变更是直接后端写越权；Admin 可绕过 Service；多项权限字段无效。结论：**当前权限边界不可靠，不能上线**。

### 3.3 文件下载是否安全

- 普通下载会通过后端 selector 和 `can_download_document()`；真实文件路径不直接返回给普通文档 API；存储层使用随机路径并防止 resolve 越界。
- Nginx 当前明确拒绝 `/data/`、`/media/`，未发现公开 MEDIA_URL/alias。
- 但临时链接未尊重回收站状态；Admin/审计/备份页面存在路径披露；尚无安全的 X-Accel internal 方案。结论：普通登录下载基本安全，临时下载仍不安全。

### 3.4 临时访问是否安全

- token 使用 32 字节随机数，数据库只存 HMAC hash；有过期、撤销、下载次数并使用 `select_for_update()` 防止并发超次数，这是正向项。
- 删除文档后仍可访问、URL 日志泄露、GET 消耗和无限上限使其不能判定为生产安全。

### 3.5 CSRF/CORS/Cookie 是否有风险

- SessionAuthentication 保持 CSRF 校验；前端从 Cookie 读取 token 并设置 `X-CSRFToken`；生产 origin 示例为精确 HTTPS 域名，没有 wildcard。
- Session Cookie HttpOnly，生产 Session/CSRF Cookie Secure，`SECURE_PROXY_SSL_HEADER` 已配置。
- 主要风险在部署闭环：当前 Nginx 没 HTTPS；若 Gunicorn 8000 暴露公网，代理头信任也会变危险。必须只允许可信 Nginx 访问 Gunicorn。

### 3.6 生产配置是否有风险

- DEBUG 在 production.py 强制 False；MySQL utf8mb4 和严格模式已设置；生产数据路径 `/data/documents`、`/data/exports` 正确，不依赖 NAS。
- `check --deploy` 实际仍报 HSTS/SSL redirect 警告；secret 没 fail-fast；部署材料不完整；备份目录未被 Git 忽略。结论：生产配置当前有上线阻断风险。

## 4. 功能专项结论

### 4.1 资料中心

- 文件夹树、列表、搜索、分页、归档只读、乐观锁、重复文件检查和版本号锁整体已有实现。
- 新版本权限是 P0；同目录重复规则与两个后端测试冲突；权限按钮与后端不一致；没有永久删除 UI。
- 文件版本能递增并指向当前版本，但模型层无法阻止 current_version 指向其他文档版本，仍依赖 Service 纪律和 Admin 收口。

### 4.2 项目资料

- 非管理员项目列表按成员关系收窄；归档后项目、文件夹、文档写入大多会被 Service 拒绝；项目删除已有自定义前置检查和文件清理，不再是裸 ModelViewSet 删除。
- manager 变更绕过成员管理是 P0；并发删除/上传仍有一致性风险；负责人 FK 与 MANAGER 成员可能分叉。

### 4.3 授权管理

- 授权记录包含创建人、权限动作、有效期、撤销状态；过期查询会自动失效；更新已禁止改绑 document/user。
- DocumentGrant 默认 DELETE 仍绕过撤销；活动授权唯一性有竞态；项目权限字段和前端 project_manager 页面与“仅管理员管理授权”的后端规则冲突。

### 4.4 回收站

- 删除为软删除，恢复检查原目录、同名/同内容冲突；永久删除仅系统管理员并要求先进入回收站。
- 临时链接没有随删除失效，是关键缺陷；永久删除前端入口缺失；物理删除失败可能留下无法从数据库追踪的孤儿文件。

### 4.5 用户管理

- 无公开注册；管理员创建用户使用 password validator；禁用、重置、改密和 WebAuthn 重置均有审计。
- 默认 DELETE、缺少最后一个管理员/禁止自我停用保护、强制改密仅前端、登录无节流仍需修复。

### 4.6 审计日志

- 已覆盖登录/登出、改密、用户、项目、成员、目录、上传、版本、下载、删除/恢复、授权、临时访问、定位、通知和备份等多数关键动作；普通用户不能查询。
- 可被管理员删除、Admin 可绕过、IP/Request-ID 可伪造、snapshot 含路径，因此当前不能称为防篡改审计。

### 4.7 定位功能预留

- 所有定位 API 需要登录；上报绑定当前用户且还要求 WebAuthn；本人只能获取自己的最新记录；只有系统管理员能看全部活动员工最新位置。
- 服务使用 latest report 和 4 小时 freshness，不是持续实时追踪；实现与“最近一次上报位置”方向一致。
- `人员位置大屏_功能说明.md` 和页面应持续使用“最近上报/最新上报”措辞，避免宣称实时定位。

## 5. 部署专项结论

### 5.1 本地开发配置

- README 的后端/前端命令与实际目录基本一致，前端默认相对 `/api/v1` 并由 Vite 代理到本机后端，没有生产硬编码后端 IP。
- `.env` 已被 Git 忽略且未发现其进入当前 Git 历史；本轮没有读取或输出其中的实际密钥。
- `npm ci` 因 Windows 上 Rolldown 原生模块被占用而 EPERM 失败，随后 `npm install` 成功；这是本机文件占用/权限问题，不是业务代码错误。

### 5.2 生产环境配置

- 已有独立 `.env.production.example`，production.py 固定 DEBUG=False；文件、导出、备份路径均可由环境变量配置并指向 `/data`。
- 需要补 fail-fast secret 检查、TLS、HSTS、端口收口和完整 systemd/Gunicorn 文档。

### 5.3 Nginx/Gunicorn 适配

- 当前 Nginx SPA fallback、`/api/` 代理和私有目录拒绝方向正确。
- 缺 TLS、Gunicorn unit/socket、超时、日志轮转和 `/protected-files/ internal`。不能直接按当前文件作为完整生产配置。

### 5.4 文件存储路径

- 第一版 `/data/documents` 与 `/data/exports` 已落实，未强制 NAS，符合约束。
- 真实文档路径不应在 API/审计/前端显示；X-Accel 方案应只传递内部 URI，不能把磁盘绝对路径发给浏览器。

### 5.5 备份

- 已覆盖 ECS 快照 + mysqldump + 文件归档 + 定期下载离机副本的方向。
- 必须先解决备份包 Git 泄露、一致性时间点、可信校验、陈旧锁和安全恢复；真实恢复演练通过前不能宣称备份可用。

### 5.6 HTTPS 配置注意点

- 80 只做 301，业务只在 443；Secure Cookie、CSRF trusted origin、WebAuthn RP/origin 必须与最终域名完全一致。
- `X-Forwarded-Proto` 只能由可信 Nginx 写入；Gunicorn 不对公网开放。
- HSTS 先短周期验证，再逐步增加，确认所有子域策略后再考虑 includeSubDomains。

## 6. 测试执行结果

所有命令均为本轮实际执行。后端目录为 `D:\vscode程序夹\wind-doc-system\backend`，前端目录为 `D:\vscode程序夹\wind-doc-system\fronted`。

### 6.1 后端

| 命令 | 结果 | 归因 |
|---|---|---|
| `D:\Anaconda\envs\doc_system\python.exe manage.py check` | 通过，0 issues | 代码/开发配置通过 |
| 注入审查用生产环境变量后 `manage.py check --deploy` | 完成但有 2 warnings：W004 HSTS、W008 SSL redirect | 生产安全配置缺口 |
| `manage.py makemigrations --check --dry-run --settings=config.settings.testing` | 通过，No changes detected | 当前模型与迁移一致；未修改历史 migration |
| `python -m pytest` | 失败：141 collected，139 passed，2 failed | 测试/业务规则契约漂移；不是环境缺失 |
| `python -m ruff check .` | 通过 | 静态规则通过 |
| `python -m ruff format --check .` | 失败：12 files would be reformatted | 格式基线问题；其中含历史 migration，不应直接重写已应用迁移 |
| `python -m mypy apps common` | 失败：23 errors in 6 files | 类型标注/动态 User 类型问题 |
| `manage.py spectacular --settings=config.settings.testing --file %TEMP%/... --validate` | 通过 | OpenAPI 生成/校验通过，未覆盖语义权限缺陷 |
| `python --version` | Python 3.12.13 | 环境信息 |
| `python -m pip check` | 通过，No broken requirements | 依赖关系完整 |
| `mysqldump --version` | MySQL Community 9.7.0；当前本机支持代码使用的关键选项 | 只验证本机工具，ECS 仍需确认 |

后端失败详情：

1. `test_grant_update_cannot_change_document_or_user`：测试在同一目录创建第二个“内容完全相同”的文件，现有重复内容规则返回 400，测试预期 201。
2. `test_batch_download_returns_zip_and_deduplicates_filenames`：测试在同一目录创建相同原始文件名，现有同名规则返回 400。若要测试 ZIP 重名，应改为不同目录中的同名文件或直接构造合法历史数据。
3. Mypy 主要集中在 WebAuthn service 参数/返回类型、动态 User 类型和 locations service 类型。
4. 格式失败包含 4 个 migration 文件；应调整格式检查范围或接受历史文件豁免，不能为了全绿修改已应用迁移。

### 6.2 前端

| 命令 | 结果 | 归因 |
|---|---|---|
| `npm ci` | 失败：EPERM，无法删除被占用的 Rolldown `.node` 文件 | 本机环境/文件占用，不是业务代码错误 |
| `npm install` | 通过；0 vulnerabilities；有原生模块清理 warning | 依赖安装成功；warning 为本机占用 |
| `npm run type-check` | 通过 | TypeScript 检查通过 |
| `npm run lint` | 通过 | ESLint 通过 |
| `npm run test:unit` | 通过：14 files，31 tests | 单元测试通过 |
| `npm run build` | 通过 | 有第三方 PURE annotation 和 >500 kB chunk 非阻断 warning |
| `npm run test:e2e` | 失败：12 tests，10 passed，2 failed | 前端落地状态/fixture 与页面行为不一致 |
| `node --version` / `npm --version` | Node v24.15.0 / npm 11.17.0 | 环境信息 |

E2E 失败详情：

1. 资料中心用例在关闭公司模块后找不到“人员名单”。
2. 授权管理用例进入 `/documents` 后找不到“详情”按钮并超时。

### 6.3 未执行或未完成的验证

- 未执行真实生产 `migrate`、`collectstatic`、Gunicorn/systemd/Nginx 启动。
- 未执行真实 MySQL 集成 pytest；当前测试使用 SQLite。
- 未执行真实 `create_system_backup`/`restore_system_backup`，避免在审查轮次产生或覆盖业务数据；只检查了代码、本机 mysqldump 版本和选项。
- 未做浏览器真实 HTTPS/WebAuthn 域名验证、并发压测、病毒扫描、SAST/DAST、第三方 Python 漏洞库审计。

## 7. 最小可上线修复路线

### 第一步：封住认证和直接写越权

1. 在后端统一强制 WebAuthn Session 和 must_change_password 状态；隔离/收口 Django Admin。
2. 修复新版本上传权限，锁定后重复校验文档状态。
3. 禁止项目负责人修改 manager，建立管理员专用负责人转移流程。
4. 删除文档后立即让所有临时访问失效。
5. 禁用 User/DocumentGrant DELETE，撤下审计删除 API/UI。

这一步不能推迟。

### 第二步：处理数据泄露和生产入口

1. 忽略并隔离 `backend/data/backups`，检查 Git 历史和提交钩子。
2. 完成 HTTPS Nginx、Gunicorn/systemd、端口收口、日志权限和 `/protected-files/ internal`。
3. 清理审计中的路径/不可信 header，启用登录限速。
4. 对生产 secret 和占位值 fail-fast。

这一步不能推迟。

### 第三步：修复一致性、备份和测试基线

1. 明确权限矩阵，处理 access_level/项目权限死字段和前后端能力位。
2. 增加数据库约束/锁，处理并发上传、授权、项目删除竞态。
3. 重做备份一致性、可信校验、陈旧锁和安全恢复，完成一次空环境恢复演练。
4. 修复后端 2 个失败、前端 2 个 E2E、Mypy 和格式范围；新增 P0 回归测试和 MySQL 集成测试。

这一步在生产上线前必须完成核心项；非关键类型清理可以按模块逐步完成，但测试基线必须明确。

### 可以推迟到上线后短期

- 大模块拆分、前端 chunk 优化。
- 细化统一响应成功 envelope。
- 低风险 UI 文案和搜索体验优化。
- 在已建立 X-Accel 和基础监控后进一步做大文件异步 ZIP。

### 绝对不能推迟

- P0 全部问题。
- WebAuthn/强制改密后端边界、版本写权限、临时链接删除状态、备份 Git 隔离、HTTPS。
- User/Grant 硬删除和审计可删除。
- 真实备份恢复演练和失败测试基线修复。

## 8. 正向确认

- 未发现公开自助注册 API。
- DRF 默认业务权限是 IsAuthenticated，公开端点集中在 CSRF、登录/WebAuthn ceremony、临时下载和 health；公开范围可识别。
- 普通文档下载走后端权限判断；文件使用随机存储路径，LocalDocumentStorage 有根目录越界检查。
- 项目/文档 QuerySet 大多先按当前用户可见范围收窄，基础 IDOR 防护方向正确。
- 临时 token 高熵、仅存 HMAC hash、支持过期/撤销/次数并发锁。
- MySQL 配置使用 utf8mb4 和严格模式，适合中文文件名和中文内容。
- production.py 强制 DEBUG=False，并启用 Secure Cookie、proxy SSL header、nosniff 和 referrer policy。
- 前端生产 API 默认 `/api/v1` 相对路径，路由守卫会等待登录态初始化；菜单按角色生成，但不能代替后端权限。
- `/data/documents`、`/data/exports`、`/data/backups` 和 ECS 快照/离机副本方向符合第一版单机部署约束，没有把 NAS、OSS、Caddy、Kubernetes 或 RDS 作为必需项。

## 9. 需人工确认的业务规则

1. 项目负责人是否允许变更负责人；若允许，旧负责人权限应立即移除、保留查看还是继续管理？
2. 所有项目成员“可上传新资料”是否也意味着“可替换现有文档版本”？本报告按两者不同权限处理。
3. restricted 文档对项目成员的查看/下载规则到底是什么；`can_download_restricted` 是否应启用。
4. 项目负责人是否应管理文件授权。当前前端允许进入，后端明确只允许系统管理员。
5. 同目录是否同时禁止“同原文件名”“同标题”“同内容”；批量 ZIP 重名场景应来自不同目录还是允许同目录同文件名。
6. 删除审计日志是否是明确合规需求。若只是清理容量，应改为不可由交互式管理员任意删除的归档/保留策略。
7. 临时下载次数是按请求、成功打开响应还是完整传输计数；当前实现按请求开始计数。
8. 用户离职后定位、通知、成员和授权历史应保留多久；在确认前不应开放用户硬删除。
