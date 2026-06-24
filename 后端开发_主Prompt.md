# Codex 计划模式主提示词：风电检测资料管理系统后端开发

你现在是本项目的资深 Python/Django 后端工程师、系统架构师和代码审查者。请在当前仓库中协助我完成“风电检测资料管理系统”的后端开发。

我是一名新手开发者，因此你的工作不仅是生成代码，还必须保证架构清晰、步骤可验证、错误可定位、每个里程碑可独立验收。当前处于 Codex 的计划模式：本轮只允许分析仓库、识别问题并输出可执行计划，不要修改文件，不要安装依赖，不要执行会改变仓库、数据库或系统状态的命令。等我明确批准某个里程碑并切换到代码模式后，再实施该里程碑。

---

## 一、当前任务

请先检查当前仓库的真实状态，包括但不限于：

1. 阅读根目录及子目录中的 `AGENTS.md`、`AGENTS.override.md`、`README.md`、`PLANS.md`、`pyproject.toml`、`requirements`、`.env.example`、Docker 配置和需求文档。
2. 查看 Git 状态、目录结构和已有代码。
3. 判断仓库是空项目、半成品项目还是已有可运行工程。
4. 不要假设某个文件已经存在；以实际仓库为准。
5. 不要删除或覆盖已有代码。
6. 若已有实现与本提示词冲突，列出冲突、影响和推荐处理方式。
7. 若仓库为空，则规划从工程初始化开始。
8. 若仓库已有代码，则规划增量实现和必要重构，不要无理由推倒重写。

本轮最终只输出完整开发计划，并等待我确认。不要直接编码。

---

## 二、系统定位

本系统是部署在公司内网的风电检测业务资料管理系统，重点管理项目资料、完工档案和企业资质文件，不是公共网盘，也不是 AI 缺陷检测平台。

当前主要资料包括：

- 完工资料档案；
- 公司资质；
- 人员资质；
- 工器具年检资质；
- 劳动防护用品资料；
- 仪器设备年检资质；
- 车辆年检及资质；
- 项目过程资料、检测报告及其他附件。

第一版主要支持：

- PDF；
- Word；
- Excel；
- 图片。

第一版暂不主动扩展到视频、大规模对象存储、全文 OCR、AI 检测、员工定位、智能调度、微服务和 Kubernetes。

---

## 三、已确定的业务规则

### 1. 用户身份

系统当前有以下身份：

1. 系统管理员；
2. 项目负责人；
3. 资料整理员；
4. 临时访问者。

代码中使用稳定英文编码，不使用中文名称参与判断。建议：

```python
system_admin
project_manager
data_operator
```

“临时访问者”第一版优先实现为限时限次下载 Token，而不是完整内部账号。除非仓库现有需求明确要求临时账号登录，否则不要为外部临时访问者创建普通用户账号。

### 2. 用户创建

这是内部系统，不开放公众自助注册。

- 用户由系统管理员创建；
- 管理员可以停用用户、重置密码；
- 用户首次登录可被要求修改密码；
- 离职用户停用而不是物理删除；
- 历史操作记录必须保留。

不要实现公开的 `/auth/register/`。

### 3. 项目负责人

项目负责人不是全局管理员。

- 项目负责人只能操作被系统管理员授权的项目；
- 项目负责人能否添加成员、管理文件夹、上传、删除、恢复、授权，由项目成员权限决定；
- 不允许仅凭全局角色自动访问所有项目。

### 4. 资料整理员

资料整理员即此前权限矩阵中的普通用户。

- 只能操作其加入的项目、被授权的文件或允许访问的公共资料；
- 不能管理全局用户和系统配置；
- 删除、恢复和授权不是天然权限，必须由项目成员权限或文件授权决定。

### 5. 文件访问级别

第一版至少分为：

```python
internal    # 内部普通文件
restricted  # 需授权文件
```

规则：

- `internal`：有效内部账号可以搜索、查看和下载，但修改、移动、删除仍需业务权限；
- `restricted`：系统管理员可直接访问，其他内部用户必须获得项目权限或明确文件授权；
- 临时访问者只能访问 Token 所指定的文件版本；
- “普通文件可以随便下载”仅指有效内部用户，不等于匿名公开。

### 6. 临时访问

临时访问必须满足：

- 一个授权明确关联一个文件版本；
- 有到期时间；
- 有最大下载次数，默认 1 次；
- 可被创建者或管理员撤销；
- 数据库只保存 Token 哈希，不保存可直接使用的明文 Token；
- 原始 Token 只在创建时返回一次；
- 并发请求不能突破下载次数限制；
- 临时用户不能搜索全站文件；
- 每次成功或失败访问都应记录审计信息。

### 7. 项目归档

项目归档后默认：

- 允许查看；
- 允许有权限用户下载；
- 禁止新增文件夹；
- 禁止上传文件；
- 禁止修改和移动文件；
- 禁止创建新版本；
- 禁止普通删除；
- 只有系统管理员可以取消归档。

### 8. 文件版本

必须区分：

- `Document`：逻辑文档；
- `DocumentVersion`：物理文件版本。

禁止用新文件覆盖旧版本。版本号自动递增，默认下载当前版本，历史版本保留。并发上传新版本时必须通过数据库事务、唯一约束和必要的行锁避免重复版本号。

### 9. 删除

普通删除是软删除：

- 文件进入回收站；
- 物理文件不立即删除；
- 记录删除人和删除时间；
- 有权限者可以恢复；
- 永久删除仅系统管理员可执行；
- 第一版不必实现自动永久清理。

### 10. 审计

至少记录：

- 登录成功、失败、退出；
- 用户创建、修改、停用、重置密码；
- 项目创建、修改、成员变更、归档；
- 文件夹创建、修改、移动、停用；
- 文件上传、下载、修改、移动、新版本、删除、恢复、永久删除；
- 内部授权创建、撤销；
- 临时授权创建、下载、撤销、过期或已消费；
- 权限拒绝；
- 系统备份和恢复结果。

日志应尽量包含操作者、时间、资源、结果、IP、User-Agent、request_id、修改前后数据和错误原因。

---

## 四、技术基线

除非仓库已有合理且已确认的不同技术选型，否则按以下基线规划：

- Python 3.12；
- Django 5.2 LTS；
- Django REST Framework；
- MySQL 8.4 LTS；
- `mysqlclient`；
- `django-filter`；
- `drf-spectacular`；
- `django-environ`；
- `django-cors-headers`；
- `Pillow`；
- `django-axes`；
- `argon2-cffi`；
- `pytest`；
- `pytest-django`；
- `pytest-cov`；
- `factory-boy`；
- `ruff`；
- `mypy`；
- `django-stubs`；
- `djangorestframework-stubs`；
- 生产环境使用 Gunicorn、Nginx、Docker Compose。

第一版不要引入：

- FastAPI；
- Celery；
- Redis；
- Elasticsearch；
- MinIO；
- Kafka；
- 微服务；
- Kubernetes。

只有确认存在当前技术无法合理解决的实际需求时，才提出增加组件，并说明收益、成本和替代方案。

---

## 五、架构原则

采用：

> 模块化单体 + 按业务 App 拆分 + Service/Selector 分层。

建议模块：

```text
accounts
projects
folders
documents
access
audit
notifications
system
common
```

职责：

- `models.py`：字段、关系、约束、索引、简单对象属性；
- `serializers.py`：输入输出结构和字段级校验；
- `services.py`：创建、修改、授权、上传、删除、归档等写操作；
- `selectors.py`：当前用户可见数据和复杂查询；
- `permissions.py`：动作级和对象级权限；
- `validators.py`：可复用文件及业务校验；
- `storage.py`：文件存储适配层；
- `views.py`：薄控制器，只负责请求编排；
- `tests/`：模型、Service、权限和 API 测试。

不得把大量业务逻辑堆入 View、Serializer、信号或模型 `save()`。

---

## 六、建议目录目标

请结合实际仓库状态评估并规划以下结构，而不是机械创建：

```text
backend/
├── manage.py
├── .env.example
├── pyproject.toml
├── pytest.ini
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── config/
│   ├── urls.py
│   ├── api_urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   └── settings/
│       ├── base.py
│       ├── development.py
│       └── production.py
├── apps/
│   ├── accounts/
│   ├── projects/
│   ├── folders/
│   ├── documents/
│   ├── access/
│   ├── audit/
│   ├── notifications/
│   └── system/
├── common/
├── data/
│   ├── files/
│   └── temporary/
├── scripts/
└── docs/
```

如果当前仓库根目录本身就是后端，不要无理由再嵌套一层 `backend/`。

---

## 七、核心数据模型要求

请在计划中给出模型关系、关键字段、约束、索引和迁移顺序。至少评估以下模型。

### 1. User

使用自定义用户模型，并且必须在首次正式迁移前设置 `AUTH_USER_MODEL`。

建议字段：

- username；
- real_name；
- employee_no；
- role；
- phone；
- email；
- is_active；
- must_change_password；
- created_at。

不得直接从 `django.contrib.auth.models` 导入固定 `User` 建立业务外键。模型外键使用 `settings.AUTH_USER_MODEL`，运行时代码使用 `get_user_model()`。

### 2. Project

建议字段：

- name；
- code，唯一；
- description；
- manager；
- status：active/archived；
- created_by；
- created_at；
- archived_at；
- archived_by。

### 3. ProjectMember

表示用户在具体项目中的身份和权限。

建议字段：

- project；
- user；
- role：manager/operator/viewer；
- can_upload；
- can_download_restricted；
- can_manage_folder；
- can_delete；
- can_restore；
- can_manage_permission；
- joined_at。

约束：

```text
(project, user) 唯一
```

请评估布尔权限字段是否足够，避免一开始设计过度复杂的通用 ACL 引擎。

### 4. Folder

这是数据库中的逻辑目录，不是物理磁盘目录。

建议字段：

- project，可为空；为空表示公司公共资料；
- parent，自关联；
- name；
- code；
- sort_order；
- is_active；
- created_by；
- created_at。

必须防止：

- 自己成为自己的父节点；
- 移入自己的后代；
- 归档项目新增或移动目录；
- 有子目录或文件时直接物理删除。

### 5. Document

建议字段：

- uuid；
- title；
- folder；
- project，可为空；
- access_level：internal/restricted；
- status：active/deleted/archived；
- description；
- owner；
- created_by；
- current_version；
- created_at；
- updated_at；
- deleted_at；
- deleted_by。

必须保证 `Document.project` 与 `Folder.project` 逻辑一致。

### 6. DocumentVersion

建议字段：

- document；
- version_no；
- storage_key；
- original_filename；
- file_size；
- mime_type；
- extension；
- sha256；
- version_comment；
- uploader；
- created_at。

约束：

```text
(document, version_no) 唯一
storage_key 唯一
```

### 7. DocumentGrant

用于内部用户的受限文件授权。

第一版优先支持用户级授权。至少考虑：

- document；
- user；
- action；
- expires_at；
- granted_by；
- created_at。

动作包括：

```text
view
download
update
delete
restore
manage
```

不要为满足所有未来可能性而过早构造庞大 ACL 框架。

### 8. TemporaryAccessGrant

建议字段：

- token_hash；
- document_version；
- recipient_name；
- recipient_contact；
- expires_at；
- max_downloads；
- download_count；
- created_by；
- created_at；
- last_downloaded_at；
- revoked_at；
- revoked_by。

需要事务和 `select_for_update()` 保护下载次数消费。

### 9. AuditLog

建议字段：

- user，可为空；
- action；
- resource_type；
- resource_id；
- result；
- ip_address；
- user_agent；
- request_id；
- before_data；
- after_data；
- error_message；
- created_at。

### 10. Notification

第一版仅系统内通知。建议字段：

- recipient；
- title；
- content；
- type；
- related_resource_type；
- related_resource_id；
- is_read；
- created_at；
- read_at。

通知失败不应回滚核心业务。

---

## 八、文件存储原则

MySQL 不保存 PDF、Word、Excel、图片的二进制本体。

- MySQL 保存元数据、路径、权限、版本和日志；
- 物理文件保存到本地数据盘或 NAS；
- 通过统一 `FileStorage` 接口隔离具体存储实现；
- 数据库只保存相对 `storage_key`，不保存 Windows 绝对路径；
- 存储键使用 UUID，不使用原始文件名；
- 下载时恢复用户看到的原始文件名；
- 文件目录不能作为匿名 `/media/` 地址公开；
- 开发环境可用 `FileResponse`；
- 生产环境规划由 Django 权限校验后通过 Nginx `X-Accel-Redirect` 发送大文件。

建议存储键：

```text
documents/{document_uuid}/{version_uuid}.{extension}
```

---

## 九、上传规则

第一版允许：

```text
.pdf
.doc
.docx
.xls
.xlsx
.jpg
.jpeg
.png
```

默认禁止可执行和脚本文件。

上传流程必须包括：

1. 验证登录和账号状态；
2. 验证项目和文件夹；
3. 验证项目未归档；
4. 验证上传权限；
5. 验证文件大小、扩展名和 MIME；
6. 使用分块读取计算 SHA-256；
7. 创建逻辑 Document；
8. 生成 storage_key；
9. 保存物理文件；
10. 创建 DocumentVersion；
11. 设置 current_version；
12. 写入审计日志；
13. 失败时清理已产生的孤立文件。

不要对大文件调用一次性 `.read()`。

数据库事务不能自动回滚物理文件，因此计划中必须包含异常清理和后续一致性检查方案。

---

## 十、搜索、下载和并发

### 1. 搜索

第一版使用 MySQL、Django ORM、合理索引和分页，不使用 Elasticsearch。

支持规划：

- 标题；
- 原始文件名；
- 项目名称和编号；
- 文件夹；
- 上传人；
- 创建时间；
- 扩展名；
- access_level；
- status。

先通过 SQL、索引、`select_related()`、`prefetch_related()` 和分页优化，再考虑搜索引擎。

### 2. 下载

所有下载必须经过后端权限判断。

- 普通文件：有效内部用户可下载；
- 受限文件：系统管理员、项目权限或 DocumentGrant；
- 临时下载：只允许 Token 指向的版本；
- 记录文档 ID、版本 ID、用户或临时授权、IP、时间和结果。

### 3. 批量下载

第一版只规划小规模批量下载，例如：

- 一次最多 20 个文件；
- 总大小上限 500MB；
- 每个文件都要单独校验权限；
- 超过限制时明确拒绝，不要同步压缩数十 GB。

### 4. 并发

必须处理：

- 两人同时上传新版本；
- 两人同时更新文件元数据；
- 同一个临时 Token 并发下载；
- 文件上传与项目归档同时发生。

版本创建和临时 Token 消费使用事务、唯一约束和行锁。元数据更新可使用 `updated_at` 进行乐观并发检查，冲突返回 HTTP 409。

---

## 十一、认证和权限

使用：

```text
Django SessionAuthentication
HttpOnly Cookie
CSRF
```

暂不使用保存在 LocalStorage 中的 JWT。

全局业务 API 默认要求登录，登录和临时下载等少数接口单独放开。

权限至少分三层：

1. 全局系统角色；
2. 项目成员权限；
3. 文件明确授权。

列表接口必须在 Selector/QuerySet 中过滤不可见数据，不能依赖前端隐藏按钮，也不能仅在详情接口做对象权限检查。

默认拒绝。无法证明允许时返回 403 或对敏感资源返回 404，避免泄露资源存在性。

---

## 十二、API 目标

统一前缀：

```text
/api/v1/
```

至少规划以下接口。

### 认证

```http
GET    /api/v1/auth/csrf/
POST   /api/v1/auth/login/
POST   /api/v1/auth/logout/
GET    /api/v1/auth/me/
POST   /api/v1/auth/change-password/
```

### 用户

```http
GET    /api/v1/users/
POST   /api/v1/users/
GET    /api/v1/users/{id}/
PATCH  /api/v1/users/{id}/
POST   /api/v1/users/{id}/disable/
POST   /api/v1/users/{id}/reset-password/
```

### 项目和成员

```http
GET    /api/v1/projects/
POST   /api/v1/projects/
GET    /api/v1/projects/{id}/
PATCH  /api/v1/projects/{id}/
POST   /api/v1/projects/{id}/archive/
POST   /api/v1/projects/{id}/unarchive/

GET    /api/v1/projects/{id}/members/
POST   /api/v1/projects/{id}/members/
PATCH  /api/v1/projects/{id}/members/{member_id}/
DELETE /api/v1/projects/{id}/members/{member_id}/
```

### 文件夹

```http
GET    /api/v1/folders/tree/
POST   /api/v1/folders/
PATCH  /api/v1/folders/{id}/
POST   /api/v1/folders/{id}/move/
POST   /api/v1/folders/{id}/disable/
```

### 文件和版本

```http
GET    /api/v1/documents/
POST   /api/v1/documents/
GET    /api/v1/documents/{id}/
PATCH  /api/v1/documents/{id}/
POST   /api/v1/documents/{id}/move/
POST   /api/v1/documents/{id}/delete/
POST   /api/v1/documents/{id}/restore/
DELETE /api/v1/documents/{id}/permanent/
GET    /api/v1/documents/{id}/download/

GET    /api/v1/documents/{id}/versions/
POST   /api/v1/documents/{id}/versions/
GET    /api/v1/documents/{id}/versions/{version_id}/download/
```

### 内部授权

```http
GET    /api/v1/documents/{id}/grants/
POST   /api/v1/documents/{id}/grants/
DELETE /api/v1/documents/{id}/grants/{grant_id}/
```

### 临时授权

```http
POST   /api/v1/documents/{id}/temporary-grants/
GET    /api/v1/documents/{id}/temporary-grants/
POST   /api/v1/temporary-grants/{id}/revoke/
GET    /api/v1/public/download/{raw_token}/
```

### 日志和通知

```http
GET    /api/v1/audit-logs/
GET    /api/v1/notifications/
POST   /api/v1/notifications/{id}/read/
POST   /api/v1/notifications/read-all/
```

请在计划中评估 REST 路径是否需要调整，但不要无理由改变业务含义。

---

## 十三、响应和错误规范

正确使用 HTTP 状态码：

```text
200 查询或修改成功
201 创建成功
204 成功且无响应体
400 参数错误
401 未登录
403 无权限
404 不存在或不可见
409 并发或业务冲突
410 临时授权过期、撤销或已消费
413 文件过大
500 服务器错误
```

错误响应建议：

```json
{
  "code": "document.concurrent_update",
  "message": "该文件已被其他用户修改，请刷新后重试",
  "errors": null,
  "request_id": "..."
}
```

不得把所有错误包装为 HTTP 200。

---

## 十四、MySQL 要求

配置必须包含：

- `utf8mb4`；
- InnoDB；
- `STRICT_TRANS_TABLES`；
- `READ COMMITTED`；
- 专用数据库和专用用户；
- 开发、测试和生产数据库分离；
- MySQL 端口不向普通办公网开放。

迁移要求：

- 自定义 User 在首次迁移前完成；
- 每个里程碑的迁移应小而可审查；
- 不要手工直接修改生产表代替 Migration；
- 计划中说明迁移顺序和依赖。

---

## 十五、测试要求

每个里程碑都必须同时实现测试，不允许最后统一补测试。

至少包括：

### 用户和认证

- 管理员可以创建用户；
- 普通用户不能创建用户；
- 停用用户不能登录；
- 密码修改和重置正确；
- 登录失败记录日志。

### 项目权限

- 项目负责人只能操作授权项目；
- 资料整理员只能看到加入的项目；
- 项目成员布尔权限生效；
- 归档项目禁止写入。

### 文件权限

- 内部用户可下载普通文件；
- 未授权用户不能下载 restricted 文件；
- 猜测文档 ID 或版本 ID 不能越权；
- DocumentGrant 到期后失效；
- 列表只返回可见数据。

### 临时授权

- Token 明文只返回一次；
- 数据库存储哈希；
- 正确 Token 可下载指定版本；
- 第二次下载失败；
- 过期失败；
- 撤销失败；
- 并发请求最多成功一次；
- 访问结果有审计日志。

### 文件和版本

- 合法文件上传成功；
- 禁止扩展名被拒绝；
- 超大文件返回 413；
- SHA-256 正确；
- 新版本自动递增；
- 并发版本号不重复；
- 上传失败清理物理文件；
- 软删除保留物理文件；
- 恢复成功；
- 永久删除仅管理员。

### 文件夹

- 树结构正确；
- 自循环被拒绝；
- 移到后代节点被拒绝；
- 归档项目不能修改文件夹。

---

## 十六、质量检查命令

请在计划中按里程碑安排以下命令，并根据仓库实际配置调整：

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
pytest
pytest --cov=apps --cov=common --cov-report=term-missing
ruff check .
ruff format --check .
mypy apps common
python manage.py spectacular --file schema.yaml --validate
```

生产阶段还要执行：

```bash
python manage.py check --deploy --settings=config.settings.production
```

不得声称测试通过，除非实际执行并看到成功结果。若因环境限制不能执行，必须明确说明未执行项和原因。

---

## 十七、文档和仓库级指令

计划中应包含：

1. 在确认后创建或更新精简的 `AGENTS.md`，记录：
   - 项目结构；
   - 环境启动命令；
   - 测试和质量检查命令；
   - 分层规则；
   - 安全不变量；
   - 禁止事项。
2. 对长周期开发建立并持续更新 `PLANS.md` 或 `docs/backend-plan.md`：
   - 当前里程碑；
   - 已完成内容；
   - 决策记录；
   - 发现的问题；
   - 测试结果；
   - 下一步。
3. 不要把所有需求全文复制进 `AGENTS.md`；使用简洁地图并链接到详细文档。
4. 关键业务规则应保存在仓库文档和测试中，而不是只存在聊天记录里。

---

## 十八、实施方式

开发必须拆成可独立验收的里程碑。推荐顺序：

### 里程碑 0：仓库和工程基线

- 工程目录；
- Git 基线；
- settings 拆分；
- 依赖文件；
- `.env.example`；
- MySQL 开发配置；
- DRF、Swagger、pytest、Ruff、mypy；
- 健康检查；
- `AGENTS.md` 和执行计划。

### 里程碑 1：自定义用户和认证

- User；
- `AUTH_USER_MODEL`；
- 第一次迁移；
- Admin；
- 用户创建、停用、重置密码；
- Session 登录、退出、me、修改密码；
- 登录保护和审计。

### 里程碑 2：项目和项目成员

- Project；
- ProjectMember；
- 成员权限；
- 项目列表过滤；
- 项目归档和取消归档；
- 权限测试。

### 里程碑 3：公共目录和项目文件夹

- Folder；
- 公共资料目录；
- 项目目录；
- 树形查询；
- 移动和循环检测；
- 初始化基础目录命令。

### 里程碑 4：文件存储、Document 和 DocumentVersion

- FileStorage；
- 上传校验；
- Document；
- DocumentVersion；
- SHA-256；
- 版本锁；
- current_version；
- 文件一致性清理；
- 上传和版本测试。

### 里程碑 5：文件查询、下载和基础权限

- internal/restricted；
- Selector；
- 搜索、筛选、排序和分页；
- 内部下载；
- 下载审计；
- 防止直接文件访问。

### 里程碑 6：内部文件授权

- DocumentGrant；
- 授权创建、撤销和过期；
- 文件级权限判定；
- 权限矩阵自动化测试。

### 里程碑 7：临时访问

- TemporaryAccessGrant；
- Token 哈希；
- 限时限次；
- 撤销；
- 行锁消费；
- 公共下载接口；
- 临时访问审计。

### 里程碑 8：移动、并发更新、回收站和永久删除

- 文档移动；
- 乐观锁；
- 软删除；
- 回收站；
- 恢复；
- 管理员永久删除。

### 里程碑 9：通知、审计查询和批量下载

- Notification；
- 审计日志查询；
- 小规模批量 ZIP；
- 限制数量和总容量。

### 里程碑 10：完整质量检查和前端交付契约

- Swagger 完整性；
- Schema 验证；
- 测试覆盖；
- 权限回归；
- 示例请求；
- 开发数据；
- 前端联调说明。

### 里程碑 11：部署准备

- production settings；
- Gunicorn；
- Nginx；
- Docker Compose；
- MySQL 和文件持久化；
- 数据库备份；
- 文件备份；
- 恢复演练文档；
- `check --deploy`。

如果当前仓库已有部分完成，请基于实际状态重排，但必须解释。

---

## 十九、本轮计划输出格式

请使用中文输出，并严格包含以下部分。

### A. 仓库现状

- 当前目录和关键文件；
- 当前可运行程度；
- 已存在模块；
- 已有依赖和配置；
- Git 状态；
- 发现的明显问题。

### B. 需求与现有代码差异

表格列出：

```text
需求
现状
差距
处理建议
是否阻塞
```

### C. 关键架构决策

逐项说明：

- 为什么采用模块化单体；
- App 拆分；
- Service/Selector 分层；
- 认证方式；
- 权限模型；
- 文件存储；
- 临时访问；
- 并发控制；
- 软删除；
- 审计；
- 暂不使用的组件。

### D. 目标目录结构

列出规划后的目录，并标记：

```text
已有
新增
修改
暂缓
```

### E. 数据模型设计

对每个模型列出：

- 目的；
- 关键字段；
- 外键；
- 唯一约束；
- 索引；
- 删除策略；
- 迁移顺序；
- 需要进一步确认的问题。

同时给出简洁关系图。

### F. 权限判定矩阵

至少覆盖：

- 系统管理员；
- 项目负责人；
- 资料整理员；
- 临时 Token；
- internal 文件；
- restricted 文件；
- active 项目；
- archived 项目；
- 上传、查看、下载、修改、删除、恢复、授权。

### G. API 规划

逐模块列出：

- 方法；
- 路径；
- 权限；
- 请求体；
- 成功状态码；
- 关键错误码；
- 对应测试。

### H. 里程碑执行计划

每个里程碑必须包含：

1. 目标；
2. 修改或新增的文件；
3. 数据库迁移；
4. 实现步骤；
5. 执行命令；
6. 自动化测试；
7. 人工验证步骤；
8. 完成标准；
9. 回滚方式；
10. 可能风险。

### I. 第一里程碑的逐文件实施清单

把我批准后最先实施的里程碑拆到文件级，说明：

```text
文件路径
准备做什么
为什么
如何验证
```

但本轮不要创建这些文件。

### J. 需要我确认的问题

只列真正阻塞数据库或权限设计的问题。

非阻塞问题请采用本提示词中的默认规则，并明确标记为“暂定假设”，不要用大量问题阻止计划输出。

### K. 最终建议

明确告诉我：

- 计划是否可以开始；
- 推荐从哪个里程碑开始；
- 批准后我应发送的下一条指令；
- 本轮未修改任何文件。

---

## 二十、工作约束

1. 当前是计划模式，不得修改文件。
2. 不要安装依赖。
3. 不要执行数据库迁移。
4. 不要启动或删除 Docker 容器。
5. 不要删除已有代码。
6. 不要泄露或写入真实密码。
7. 不要创建公开自助注册。
8. 不要把文件二进制存入 MySQL。
9. 不要将真实文件目录直接公开。
10. 不要仅靠前端控制权限。
11. 不要一次性规划为微服务。
12. 不要为了展示技术而引入非必要组件。
13. 不要声称命令已通过，除非实际执行过。
14. 发现歧义时区分“阻塞问题”和“可暂定假设”。
15. 输出必须足够具体，使后续代码模式可以按里程碑直接执行。
16. 计划完成后停止，等待我批准，不要自动进入编码。

现在开始：先勘察仓库，只进行只读分析，然后按照上述格式输出完整后端开发计划。
