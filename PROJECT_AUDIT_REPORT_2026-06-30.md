# wind-doc-system 全量审计报告

审计时间：2026-06-30  
审计范围：`D:\vscode程序夹\wind-doc-system` 当前工作树  
审计方式：代码审计、OpenAPI 契约核对、后端测试、前端类型/静态/单元/构建/e2e 验证。  
处理原则：仅检查和记录问题，未修改业务代码；本文件为本次审计输出。

## 当前工作树状态

审计开始前仓库已有未提交修改，以下文件不是本次审计修复产生：

- `backend/apps/documents/services.py`
- `backend/apps/documents/tests/test_document_lifecycle_api.py`
- `backend/apps/documents/tests/test_document_query_download_api.py`
- `backend/apps/documents/tests/test_document_upload_api.py`
- `backend/apps/folders/services.py`
- `backend/apps/folders/tests/test_folder_api.py`
- `backend/apps/system/management/commands/seed_dev_data.py`
- `fronted/e2e/app.spec.ts`
- `fronted/src/modules/documents/api/folders.api.ts`
- `fronted/src/modules/documents/components/DocumentExplorer.vue`
- `fronted/src/modules/documents/pages/DocumentCenterPage.vue`
- `fronted/src/modules/documents/utils/folders.ts`
- `fronted/src/modules/documents/utils/public-root-folders.ts`
- `fronted/src/styles/index.scss`
- `fronted/tests/unit/folder-options.spec.ts`
- `fronted/tests/unit/public-root-folders.spec.ts`

## 验证结果

通过：

- `D:\Anaconda\envs\doc_system\python.exe manage.py check`：通过。
- `D:\Anaconda\envs\doc_system\python.exe manage.py makemigrations --check --dry-run`：通过，无待生成迁移。
- `D:\Anaconda\envs\doc_system\python.exe -m ruff check .`：通过。
- `D:\Anaconda\envs\doc_system\python.exe -m pytest`：94 passed。
- `npm run type-check`：通过。
- `npm run lint`：通过。
- `npm run test:unit`：10 个测试文件、16 个用例通过。
- `npm run build`：通过；存在 Rolldown `INVALID_ANNOTATION` 和 chunk 大小警告。

失败：

- `npm run test:e2e`：11 个 Playwright 用例中 10 passed、1 failed。
- 失败用例：`fronted/e2e/app.spec.ts:315`，`manages document grants and temporary access from document detail`。
- 失败位置：`fronted/e2e/app.spec.ts:394` 等待 `getByRole('button', { name: '详情' })` 超时。
- 失败页面实际停留在“公司名单 / 公司数：0 / 添加公司”，没有文档表格与“详情”按钮。

## P0 必须优先处理

### P0-1 项目默认硬删除接口暴露，普通可见项目成员可能删除项目

证据：

- `backend/apps/projects/views.py:26` 使用 `class ProjectViewSet(viewsets.ModelViewSet)`。
- `backend/apps/projects/views.py:29` 权限为 `IsAuthenticated`。
- `backend/apps/projects/views.py:36-39` 只对 `create` 特判系统管理员，其余动作回到默认权限。
- 文件中没有 `destroy()` / `perform_destroy()` 覆盖。
- `backend/docs/openapi.yaml:1196` 暴露 `/api/v1/projects/{id}/`。
- `backend/docs/openapi.yaml:1280-1281` 暴露 `DELETE` / `v1_projects_destroy`。

影响：

- `ModelViewSet` 默认提供 `destroy`。
- `get_queryset()` 返回当前用户可见项目；非系统管理员只要是项目成员就可能命中对象。
- 这条路径绕过 `archive_project()`、`can_manage_project()`、审计日志和归档保护语义。
- 如果数据库外键允许删除，会造成项目、成员、目录、文档等级联数据丢失；即使被外键阻止，也会形成未设计的 500/保护异常路径。

建议：

- 明确禁用 `DELETE /api/v1/projects/{id}/`，或重写为有权限、审计和业务校验的显式服务。
- 为 viewer/operator/project_manager/system_admin 分别增加项目删除权限测试。
- OpenAPI 删除未支持动作，避免前后端误接入。

### P0-2 目录默认硬删除接口暴露，绕过停用规则和目录权限

证据：

- `backend/apps/folders/views.py:19` 使用 `class FolderViewSet(viewsets.ModelViewSet)`。
- `backend/apps/folders/views.py:22` 权限为 `IsAuthenticated`。
- `backend/apps/folders/views.py:35-85` 仅实现 create/update/move/disable，没有覆盖 `destroy()`。
- `backend/apps/folders/services.py:101-124` 的 `disable_folder()` 才检查系统根、目录管理权限、启用子目录和资料存在性。
- `backend/docs/openapi.yaml:846` 暴露 `/api/v1/folders/{id}/`。
- `backend/docs/openapi.yaml:930-931` 暴露 `DELETE` / `v1_folders_destroy`。

影响：

- 任何非临时用户可见的公共目录、项目成员可见的项目目录，都可能通过默认 DELETE 进入硬删除。
- 默认硬删除绕过 `can_manage_folder()`、`is_system_root` 保护、`disable_folder()` 业务规则和审计日志。
- 空目录风险最大；有子目录或文档时可能由外键保护抛出未设计异常。

建议：

- 禁用 `DELETE /api/v1/folders/{id}/`，仅保留 `POST /disable/`。
- 如果确需硬删除，必须走服务层，且至少复用停用权限、系统根保护、子目录/文档保护、审计日志。
- 增加普通项目成员、无目录管理权限成员、公共目录、系统根目录的 DELETE 回归测试。

### P0-3 文档授权更新可改绑 document/user，存在越权授权风险

证据：

- `backend/apps/access/views.py:14` 使用 `class DocumentGrantViewSet(viewsets.ModelViewSet)`。
- `backend/apps/access/views.py:40-46` `perform_update()` 将 `serializer.validated_data` 原样传给服务。
- `backend/apps/access/services.py:37-44` `update_document_grant()` 只对更新前的 `grant.document` 调用 `_ensure_manage_allowed()`。
- `backend/apps/access/services.py:59-61` 随后对 `data.items()` 全量 `setattr()` 并保存。
- `backend/apps/access/serializers.py:19-41` `fields` 包含 `document` 和 `user`。
- `backend/apps/access/serializers.py:43-57` `read_only_fields` 未包含 `document` 和 `user`。

影响：

- 攻击者只要能管理某个旧授权，就可能通过 PATCH/PUT 把该授权的 `document` 改到另一个受限文档，或把 `user` 改成其他账号。
- 服务层权限校验发生在字段改绑前，没有对新文档重新校验管理权限。
- 前端当前编辑授权时没有发送 `document/user`，但后端 API 可被直接调用，不能依赖前端约束。

建议：

- 更新接口禁止修改 `document` 和 `user`，将其加入 `read_only_fields` 或拆分创建/更新 serializer。
- 如果业务需要迁移授权对象，必须对新旧文档都做管理权限校验，并写审计。
- 增加测试：有 A 文档管理权但无 B 文档管理权的用户，不能把授权从 A 改绑到 B。

## P1 高优先级

### P1-1 文档授权默认硬删除绕过撤销和审计

证据：

- `backend/apps/access/views.py:14` 使用 `ModelViewSet`。
- `backend/apps/access/views.py:50-57` 提供显式 `revoke()`，但未禁用默认 `destroy()`。
- `backend/apps/access/services.py:74-96` `revoke_document_grant()` 负责写撤销人、撤销时间和审计。
- `backend/docs/openapi.yaml:248` 暴露 `/api/v1/document-grants/{id}/`。
- `backend/docs/openapi.yaml:332-333` 暴露 `DELETE` / `v1_document_grants_destroy`。

影响：

- 可管理授权的用户可以硬删除授权记录，绕过 `revoked_at`、`revoked_by` 和审计日志。
- 历史授权状态不可追溯，审计中心无法解释权限变更。

建议：

- 禁用 `DELETE /api/v1/document-grants/{id}/`，只允许 `POST /revoke/`。
- 增加 DELETE 不可用或返回 405/403 的测试。

### P1-2 用户默认硬删除暴露，与“停用用户”语义冲突且缺审计

证据：

- `backend/apps/accounts/views.py:145` 使用 `class UserViewSet(viewsets.ModelViewSet)`。
- `backend/apps/accounts/views.py:147` 系统管理员可访问。
- `backend/apps/accounts/views.py:170-183` 已提供 `disable` 和 `reset-password`，但没有覆盖 `destroy()`。
- `backend/docs/openapi.yaml:1712` 暴露 `/api/v1/users/{id}/`。
- `backend/docs/openapi.yaml:1796-1797` 暴露 `DELETE` / `v1_users_destroy`。

影响：

- 系统管理员可硬删除用户，绕过 `disable_user()` 的审计路径。
- 历史项目成员、审计日志、文档创建人等外键虽然多为 SET_NULL/CASCADE/PROTECT，但硬删除会破坏追溯性。

建议：

- 禁用用户硬删除，保留停用。
- 如业务确需删除，必须走服务层，限制不能删除自己/最后一个管理员，并完整审计。

### P1-3 已删除文档仍可能生成或消费临时访问链接

证据：

- 普通下载在 `backend/apps/documents/services.py:173-174` 显式拒绝 `document.is_deleted`。
- 临时访问创建在 `backend/apps/access/temporary_services.py:33-50` 只取 `document_version.document` 并创建授权，未检查 `document.is_deleted`。
- 临时访问消费在 `backend/apps/access/temporary_services.py:98-168` 校验 token 是否有效、次数、文件是否存在，但未检查所属文档是否已删除。
- `backend/apps/access/selectors.py:40-49` 可管理文档集合基于 `Document.objects.all()`，未排除回收站文档。
- 前端回收站使用 `fronted/src/modules/documents/pages/RecycleBinPage.vue:12` 的 `DocumentExplorer mode="trash"`。
- 文档详情始终挂载授权面板：`fronted/src/modules/documents/components/DocumentDetailDrawer.vue:70-71`。
- 授权面板只判断当前版本存在：`fronted/src/modules/access/components/DocumentAccessPanel.vue:41`、`257`、`314-316`。

影响：

- 软删除后本应不可下载的文件，可能通过已有或新建的临时访问链接继续外部下载。
- 这会削弱回收站/软删除的访问控制语义。

建议：

- 创建临时访问、消费临时访问时都拒绝 `document.is_deleted`。
- 回收站详情不展示授权管理入口，或禁用授权/临时访问操作。
- 增加已删除文档临时访问创建和下载测试。

### P1-4 当前 e2e 失败，授权管理详情流程未被端到端保护

证据：

- `npm run test:e2e` 失败 1 个用例。
- 失败用例：`fronted/e2e/app.spec.ts:315`。
- 失败位置：`fronted/e2e/app.spec.ts:394` 等待“详情”按钮超时。
- 失败页面快照显示当前在“公司名单 / 公司数：0”，没有文档结果区。

影响：

- 文档详情中的“授权管理 / 临时访问”关键流程当前没有通过 e2e。
- 这会掩盖前端对授权接口、临时链接生成、文档详情抽屉的回归问题。

建议：

- 修正该用例的目录 fixture 或初始选择逻辑，使测试能进入文档表格。
- 将授权管理 e2e 拆出更明确的 fixture，避免被公司/人员目录落地页行为影响。

## P2 中优先级

### P2-1 前端项目管理页面没有按角色隐藏敏感操作按钮

证据：

- 菜单允许 `system_admin/project_manager/data_operator` 进入项目管理：`fronted/src/core/router/menu-builder.ts:32`。
- 项目路由没有 `roles` 限制：`fronted/src/core/router/index.ts` 的 `projects` 和 `project-detail` meta 只要求登录。
- `fronted/src/modules/projects/pages/ProjectListPage.vue:84` 始终显示“创建项目”。
- `fronted/src/modules/projects/pages/ProjectListPage.vue:92-95` 始终绑定编辑。
- `fronted/src/modules/projects/pages/ProjectDetailPage.vue:184-203` 始终显示添加成员、成员编辑/删除、归档/取消归档入口。

影响：

- 后端会拒绝无权限用户，但用户会频繁点到 403/错误提示。
- 对“不同用户进入系统后，对应操作权限正确”的体验要求不充分。

建议：

- 前端引入当前用户角色和项目成员权限，按 `can_manage_permission`、`can_manage_project`、系统管理员等条件隐藏或禁用按钮。
- 后端仍作为最终权限边界。

### P2-2 前端文档表格显示所有资料写操作，缺少按文档权限的 UI 收敛

证据：

- `fronted/src/modules/documents/components/DocumentTable.vue:76-80` 始终显示下载、修改、移动、新版本、删除。
- `fronted/src/modules/documents/components/DocumentTable.vue:73` 回收站模式始终显示恢复。
- `fronted/src/modules/documents/components/DocumentExplorer.vue:156` `canUpload` 仅判断是否回收站/是否目录落地页，不判断项目上传权限。

影响：

- 无下载、无上传、无删除、无恢复权限的用户仍会看到操作按钮。
- 安全上依赖后端拦截；体验上不符合不同角色操作权限清晰可见的要求。

建议：

- 后端列表返回每条文档的 `permissions`/`allowed_actions`，或前端基于项目成员权限和文档授权计算按钮可见性。
- 增加 project viewer/data operator/restricted grant 用户的前端按钮测试。

### P2-3 前端错误归一化没有正确展开后端标准错误结构的 field errors

证据：

- 后端统一错误结构为 `{ code, message, errors, request_id }`：`backend/common/exceptions.py:19-23`。
- 前端 `readDetail()` 会读取 `message`：`fronted/src/core/http/error-normalizer.ts:50-58`。
- 前端 `readFieldErrors()` 从顶层对象抽字段：`fronted/src/core/http/error-normalizer.ts:61-72`，没有读取 `data.errors`。

影响：

- 后端 serializer 字段错误会被包在 `errors` 中，前端表单级字段错误无法正常映射。
- 用户只看到泛化错误提示，不利于修正输入。

建议：

- 前端优先读取 `data.errors` 作为字段错误来源。
- 单测覆盖后端当前标准错误结构。

### P2-4 高风险权限问题缺少回归测试覆盖

证据：

- 现有后端测试 94 个全部通过。
- 搜索现有测试未发现 `client.delete` 覆盖项目、目录、用户、文档授权默认硬删除。
- 授权更新测试未覆盖 `document/user` 改绑越权场景。

影响：

- 当前测试通过不能证明敏感增删改权限正确。
- 后续重构可能继续保留或扩大默认 `ModelViewSet` 暴露面。

建议：

- 增加后端权限矩阵测试：system_admin/project_manager/data_operator/temporary_user/项目 viewer/operator/带 grant 用户。
- 对每个写操作至少覆盖成功、无权限、跨项目、已归档、已删除/停用对象。

## P3 清理与加固建议

### P3-1 本地运行产物和测试数据需要清理策略

当前存在但均被 `.gitignore` 忽略：

- `backend/data/files/` 下 7 个 `.bin` 文件，约 4,740,168 bytes。
- `fronted/dist/` 下 25 个构建产物，约 1,552,857 bytes。
- `fronted/playwright-report/` 与 `fronted/test-results/`，约 565,736 bytes。
- `fronted/node_modules/`。
- `backend/.mypy_cache/`、`backend/.pytest_cache/`、`backend/.ruff_cache/`。
- `backend/.env`。

影响：

- 不影响 Git 入库，但会污染本地打包、压缩交接和人工检查视野。
- `backend/data/files/` 中的 `.bin` 很可能是开发/测试上传残留，和用户提到的“已无用测试数据”匹配。

建议：

- 交接或打包前清理忽略产物，仅保留 `.gitkeep`。
- 若需要长期保留本地演示数据，应在 README 中明确其用途和清理命令。

### P3-2 seed_dev_data 存在固定演示账号和 --force

证据：

- `backend/apps/system/management/commands/seed_dev_data.py:20` 固定 `DEV_PASSWORD = "Password123!"`。
- `backend/apps/system/management/commands/seed_dev_data.py:29-34` 支持 `--force` 在非 DEBUG 环境执行。
- `backend/apps/system/management/commands/seed_dev_data.py:36-37` 非 DEBUG 且无 `--force` 会拒绝。

影响：

- 默认保护存在，但 `--force` 仍可能在非一次性环境注入固定账号和演示数据。

建议：

- 保留开发命令可以，但生产部署文档需明确禁止执行。
- 如后续强化，可要求 `--force` 再附加环境变量确认或删除生产可执行路径。

### P3-3 登录缺少节流/锁定策略

证据：

- `backend/apps/accounts/views.py:45-77` 登录失败仅审计并返回错误。
- `backend/config/settings/base.py:121` REST_FRAMEWORK 未配置 throttle。

影响：

- 内网系统也应考虑密码爆破、误操作和审计噪声。

建议：

- 增加登录失败节流、账号锁定或验证码策略。
- 增加失败次数和 IP 维度审计查询。

### P3-4 API 文档和 schema 当前直接挂载

证据：

- `backend/config/urls.py:7-8` 直接暴露 `/api/schema/` 和 `/api/docs/`。

影响：

- 如果生产环境对外可达，API 结构会被直接枚举。

建议：

- 生产环境限制为系统管理员、内网 IP、或关闭 Swagger UI。

### P3-5 上传校验主要依赖扩展名

证据：

- `backend/common/validators.py:7-16` 定义允许扩展名。
- `backend/common/validators.py:29-42` 校验文件名、扩展名、大小。

影响：

- 扩展名可以伪造；当前更偏向业务文件白名单，而不是内容安全校验。

建议：

- 后续增加 MIME/magic number 检测、病毒扫描、文件预览隔离策略。

## 正向确认

- 后端全局 DRF 默认权限为登录用户：`backend/config/settings/base.py:121-128`。
- 后端使用 SessionAuthentication，前端 Axios `withCredentials` 并注入 CSRF header。
- 系统健康检查 `GET /api/v1/health/` 允许匿名，符合健康探测常见设计。
- 文档普通下载、批量下载、更新、移动、软删除、恢复、永久删除都有服务层权限校验和审计路径。
- 项目成员管理的删除已显式重写 `destroy()` 并走服务层审计；问题主要集中在未重写的默认 `ModelViewSet.destroy`。

## 建议修复顺序

1. 禁用或重写项目、目录、文档授权、用户的默认硬删除接口。
2. 修复文档授权更新的 `document/user` 改绑越权。
3. 修复已删除文档临时访问创建/下载缺少 `is_deleted` 校验。
4. 补齐上述后端权限矩阵测试。
5. 修复当前失败的 e2e 授权管理用例。
6. 前端按角色/项目成员权限收敛按钮展示。
7. 清理本地测试数据和构建产物，完善交接清理说明。
