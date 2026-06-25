1. 目标：建立可运行 Django 后端骨架和质量工具。
2. 文件：新增 `backend/manage.py`、`config/`、`requirements/`、`pyproject.toml`、`pytest.ini`、`.env.example`、`common/`、`apps/system/`、`AGENTS.md`、`PLANS.md`。
3. 迁移：无业务迁移。
4. 步骤：初始化 Django 配置；拆分 settings；配置 DRF、CORS、spectacular、pytest、ruff、mypy；新增健康检查。
5. 命令：`python manage.py check`、`ruff check .`、`ruff format --check .`、`pytest`。
6. 自动化测试：健康检查 API、settings import、URL schema 基础测试。
7. 人工验证：访问 `/api/v1/health/` 和 Swagger schema。
8. 完成标准：工程可启动检查，无业务表迁移。
9. 回滚：删除新增工程文件；因当前无既有代码，风险低。
10. 风险：本机未安装依赖时命令可能无法执行，需先由用户批准安装。

### 里程碑 1：自定义用户和认证

1. 目标：完成内部账号、管理员创建用户、Session 登录和认证审计。
2. 文件：`apps/accounts/`、`apps/audit/`、认证 URL、settings。
3. 迁移：先 `accounts.User`，再 `audit.AuditLog`。
4. 步骤：自定义用户；Admin；登录/退出/me/改密；管理员用户管理；失败审计。
5. 命令：`python manage.py makemigrations --check --dry-run`、`python manage.py check`、`pytest`、`ruff`。
6. 测试：管理员创建用户、普通拒绝、停用不能登录、重置密码、登录失败审计。
7. 人工验证：用管理员账号创建用户并登录。
8. 完成标准：无公开注册；所有业务 API 默认登录保护。
9. 回滚：迁移回滚到 0，仅在开发库执行。
10. 风险：`AUTH_USER_MODEL` 必须在首次正式迁移前固定。

### 里程碑 2：项目和项目成员

1. 目标：项目、成员、布尔权限和归档规则。
2. 文件：`apps/projects/`、权限工具、审计接入。
3. 迁移：`Project` 后 `ProjectMember`。
4. 步骤：项目 CRUD；成员 CRUD；Selector 列表过滤；归档/取消归档。
5. 命令：迁移 dry-run、check、pytest、ruff、mypy。
6. 测试：项目负责人只看授权项目；布尔权限；归档禁止写入。
7. 人工验证：创建项目和成员，切换用户验证可见范围。
8. 完成标准：项目负责人无全局项目权限。
9. 回滚：回滚 projects 迁移。
10. 风险：项目负责人默认权限模板需按 J 中确认或暂定值执行。

### 里程碑 3：公共目录和项目文件夹

1. 目标：实现数据库逻辑目录和树查询。
2. 文件：`apps/folders/`、初始化目录命令。
3. 迁移：`Folder`。
4. 步骤：公共/项目目录；树查询；移动；自循环和后代检测；归档保护。
5. 命令：check、pytest、ruff、mypy。
6. 测试：树结构、自循环、移入后代、归档项目拒绝。
7. 人工验证：创建公共目录和项目目录。
8. 完成标准：目录不是物理磁盘目录。
9. 回滚：回滚 folders 迁移。
10. 风险：大量层级目录性能后续需优化。

### 里程碑 4：文件存储、Document 和 DocumentVersion

1. 目标：上传、版本、SHA-256、存储隔离。
2. 文件：`apps/documents/`、`common/storage.py`、`common/validators.py`。
3. 迁移：`Document` 后 `DocumentVersion`，再加 `current_version` 关系。
4. 步骤：文件校验；分块计算哈希；保存物理文件；创建版本；失败清理孤立文件；版本行锁。
5. 命令：check、makemigrations dry-run、pytest、ruff、mypy。
6. 测试：合法上传、扩展名拒绝、超大文件 413、SHA、并发版本号不重复、失败清理。
7. 人工验证：上传 PDF/Word/Excel/图片。
8. 完成标准：不覆盖旧版本，不把二进制存 MySQL。
9. 回滚：迁移回滚并清理开发存储目录。
10. 风险：事务无法回滚物理文件，必须实现异常清理和一致性检查。

### 里程碑 5：文件查询、下载和基础权限

1. 目标：internal/restricted 基础访问、搜索、分页、下载审计。
2. 文件：`apps/documents/selectors.py`、`permissions.py`、下载视图。
3. 迁移：必要索引迁移。
4. 步骤：可见 QuerySet；筛选排序；当前版本下载；权限拒绝审计。
5. 命令：pytest、coverage、ruff、mypy、spectacular validate。
6. 测试：内部文件下载、restricted 拒绝、猜 ID 不越权、列表过滤。
7. 人工验证：不同用户搜索和下载。
8. 完成标准：所有下载经后端权限判断。
9. 回滚：移除 API 和索引迁移。
10. 风险：搜索性能依赖 MySQL 索引和分页设计。

### 里程碑 6：内部文件授权

1. 目标：DocumentGrant 用户级授权。
2. 文件：`apps/access/`、文件权限判定集成。
3. 迁移：`DocumentGrant`。
4. 步骤：授权创建、查询、撤销、过期判定；审计。
5. 命令：check、pytest、ruff、mypy。
6. 测试：view/download/update/delete/restore/manage，各 action 到期失效。
7. 人工验证：给非项目成员授予 restricted 下载。
8. 完成标准：不引入过度 ACL 引擎。
9. 回滚：回滚 access 迁移。
10. 风险：授权历史如需长期保留，后续可加 revoked 字段。

### 里程碑 7：临时访问

1. 目标：限时限次 Token 下载指定版本。
2. 文件：`apps/access/temporary_*`、公开下载 URL。
3. 迁移：`TemporaryAccessGrant`。
4. 步骤：生成随机 Token；存哈希；只返回一次；撤销；`select_for_update()` 消费次数。
5. 命令：pytest 含并发测试、ruff、mypy。
6. 测试：正确下载一次、第二次失败、过期、撤销、并发最多成功一次、审计。
7. 人工验证：复制创建时返回的 token 下载。
8. 完成标准：临时访问不能搜索全站。
9. 回滚：回滚临时授权迁移。
10. 风险：并发测试需稳定隔离测试数据库。

### 里程碑 8：移动、并发更新、回收站和永久删除

1. 目标：文件移动、乐观锁、软删除、恢复、永久删除。
2. 文件：documents services/selectors/permissions。
3. 迁移：必要状态和索引补充。
4. 步骤：移动一致性；`updated_at` 冲突；回收站列表；永久删除清理物理文件。
5. 命令：pytest、coverage、ruff、mypy。
6. 测试：409 冲突、软删除保留物理文件、恢复、永久删除仅管理员。
7. 人工验证：两浏览器模拟并发编辑。
8. 完成标准：普通删除不物理删。
9. 回滚：回滚补充迁移。
10. 风险：永久删除与版本文件清理需幂等。

### 里程碑 9：通知、审计查询和批量下载

1. 目标：通知中心、审计查询、小规模 ZIP。
2. 文件：`apps/notifications/`、audit 查询 API、documents batch download。
3. 迁移：`Notification`。
4. 步骤：通知 CRUD；审计 filters；批量下载 20 个/500MB 限制。
5. 命令：pytest、coverage、ruff、mypy。
6. 测试：通知已读、审计过滤、批量逐文件权限、超限拒绝。
7. 人工验证：批量选择文件下载。
8. 完成标准：不同步压缩超大文件。
9. 回滚：回滚 notifications 迁移，移除批量 API。
10. 风险：ZIP 文件名冲突需处理。

### 里程碑 10：完整质量检查和前端交付契约

1. 目标：稳定 API 契约和开发数据。
2. 文件：schema、docs、示例请求、测试补强。
3. 迁移：无或仅数据命令。
4. 步骤：完善 Swagger；示例请求；权限回归；开发种子数据命令。
5. 命令：`pytest --cov=apps --cov=common --cov-report=term-missing`、`python manage.py spectacular --file schema.yaml --validate`。
6. 测试：全量回归。
7. 人工验证：按前端流程跑通认证、项目、上传、授权、下载。
8. 完成标准：前端可按 OpenAPI 联调。
9. 回滚：撤回文档/示例变更。
10. 风险：前端需求可能推动字段命名调整。

### 里程碑 11：部署准备

1. 目标：生产配置、Docker Compose、Gunicorn、Nginx、备份恢复文档。
2. 文件：`deploy/`、production settings、Dockerfile、compose、Nginx 配置、备份脚本文档。
3. 迁移：无业务迁移。
4. 步骤：生产 env；MySQL 持久化；文件持久化；备份恢复演练；`X-Accel-Redirect`。
5. 命令：`python manage.py check --deploy --settings=config.settings.production`。
6. 测试：生产 settings import、静态/媒体保护、健康检查。
7. 人工验证：预生产环境启动和恢复演练。
8. 完成标准：内网部署说明完整。
9. 回滚：回退 deploy 配置。
10. 风险：本轮禁止 Docker 操作，部署验证需单独批准。
