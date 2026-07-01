# 前端交付说明

本文档描述当前后端可供前端联调的稳定契约。以代码和 OpenAPI 为准，配套文件：

- `backend/docs/openapi.yaml`：OpenAPI 3 schema，可导入 Apifox、Swagger UI 或生成客户端。
- `backend/docs/api_examples.md`：按业务流程组织的请求示例。
- `python manage.py seed_dev_data`：开发环境幂等种子数据。

## 运行与认证

- API 前缀：`/api/v1/`
- 认证方式：Django Session + CSRF。
- 浏览器前端必须使用 cookie：
  - `fetch`：`credentials: "include"`
  - axios：`withCredentials: true`
- 写请求必须带 `X-CSRFToken`。先请求 `GET /api/v1/auth/csrf/`，从响应 `csrfToken` 或 `csrftoken` cookie 中读取。
- 登录：`POST /api/v1/auth/login/`，成功后后端写入 session cookie。
- 当前用户：`GET /api/v1/auth/me/`
- 退出：`POST /api/v1/auth/logout/`

## 通用响应约定

- 列表接口使用 DRF 分页：
  - `count`
  - `next`
  - `previous`
  - `results`
- 常用查询参数：
  - `page`
  - `search`
  - `ordering`，例如 `ordering=-updated_at`
  - 模型字段过滤，例如 `project=1`、`folder=2`、`access_level=restricted`
- 常见错误：
  - `400`：参数或业务状态不合法。
  - `401`：未登录。
  - `403`：无权限。
  - `404`：资源不存在或对当前用户不可见。
  - `409`：乐观锁冲突，刷新详情后重试。
  - `413`：上传或批量下载大小超限。
- 错误体通常包含 `detail` 或字段级错误；前端应优先展示字段错误，否则展示 `detail`。

## 角色与权限

系统角色：

- `system_admin`：系统管理员，可管理用户、项目、公共目录、审计查询。
- `project_manager`：项目负责人角色，实际项目权限由 `ProjectMember` 决定。
- `data_operator`：普通资料操作用户。

项目成员权限字段：

- 上传文档、新增版本不再依赖项目成员权限；登录用户在可见资料目录内均可上传。
- `can_download_restricted`：下载项目内受限文档。
- `can_manage_folder`：管理项目文件夹。
- `can_delete`：软删除文档。
- `can_restore`：恢复回收站文档。
- `can_manage_permission`：管理 `DocumentGrant` 和临时访问。

文档访问级别：

- `internal`：项目成员或公共目录可见。
- `restricted`：需要项目受限下载权限或 `DocumentGrant` 用户级授权。

## 前端核心流程

1. 初始化登录态：`auth/csrf` -> `auth/login` -> `auth/me`。
2. 项目页：`GET /projects/` 展示当前用户可见项目。
3. 目录树：`GET /folders/tree/?project_id=<id>`；公共目录可不传项目。
4. 文档列表：`GET /documents/?project=<id>&folder=<id>&search=...`。
5. 上传文档：`POST /documents/`，`multipart/form-data` 字段为 `folder`、`file`、`title`、`description`、`access_level`。
6. 新增版本：`POST /documents/{id}/versions/`，`multipart/form-data` 字段为 `file`。
7. 编辑/移动/删除/恢复：先读详情中的 `updated_at`，请求体传 `expected_updated_at`。
8. 下载：`GET /documents/{id}/download/`，以 blob 处理响应，并解析 `Content-Disposition`。
9. 授权：受限文档通过 `/document-grants/` 做用户级授权。
10. 临时访问：`POST /temporary-access-grants/` 创建后只在创建响应返回明文 `token` 和 `download_url`。
11. 通知中心：`GET /notifications/`、`POST /notifications/{id}/read/`、`POST /notifications/{id}/unread/`。
12. 审计页：系统管理员访问 `GET /audit-logs/`。

## 乐观锁

以下接口必须传 `expected_updated_at`：

- `PATCH /api/v1/documents/{id}/`
- `PUT /api/v1/documents/{id}/`
- `POST /api/v1/documents/{id}/move/`
- `POST /api/v1/documents/{id}/delete/`
- `POST /api/v1/documents/{id}/restore/`
- `POST /api/v1/documents/{id}/permanent-delete/`

如果返回 `409`，说明文档已被其他用户或操作更新。前端处理策略：重新拉取详情，提示用户确认后重试。

## 文件接口注意事项

- 普通下载和批量下载返回二进制流，不是 JSON。
- 批量下载接口：`POST /api/v1/documents/batch-download/`，请求体 `{"document_ids":[1,2]}`。
- 批量限制：最多 20 个文档，未压缩总大小不超过 500MB。
- 上传限制由后端 `MAX_UPLOAD_SIZE_MB` 控制，默认 200MB。
- 允许的扩展名以 `common/validators.py` 为准，前端可以做预校验，但不能替代后端校验。

## 开发种子数据

在 `backend/` 目录执行：

```powershell
python manage.py migrate
python manage.py seed_dev_data
```

固定账号：

| 用户名 | 密码 | 用途 |
| --- | --- | --- |
| `admin` | `Password123!` | 系统管理员 |
| `manager` | `Password123!` | 项目负责人，具备完整项目权限 |
| `operator` | `Password123!` | 资料整理员，可上传、管理文件夹、删除和恢复 |
| `viewer` | `Password123!` | 查看者，并被授予一个受限文档下载权限 |

固定项目：`DEMO-FRONTEND` / `前端联调示例项目`。

该命令可重复执行。默认只允许 `DEBUG=True` 环境运行。
