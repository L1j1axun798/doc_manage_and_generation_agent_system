# 风电检测资料管理系统

面向公司内部办公场景的风电检测资料管理系统。当前代码是 Django 模块化单体后端 + Vue 3 前端，支持用户与权限、项目、文件夹、文档版本、临时访问、审计、人员定位、通知，以及受控的“入场资料编制（四措两案）” Document Agent。

## 1. 先看结论

- 后端：Python 3.12、Django 5.2、Django REST Framework、MySQL。
- 前端：Vue 3、TypeScript、Vite、Element Plus、Pinia。
- 异步任务：Redis + RQ。Document Agent 的事实提取、章节生成在 Worker 中执行。
- 文件正文不存 MySQL，存放在 `FILE_STORAGE_ROOT`；MySQL 保存元数据、权限、任务、审计等。
- API 默认要求登录。文件下载必须经过后端权限判断。
- 本地前端地址固定为 `http://localhost:5174`。启用 WebAuthn 时不要改成 `127.0.0.1`。
- Document Agent 默认关闭。真实模型、Embedding、Phase 5 验收门禁全部满足后才能在生产启用。

## 2. 本地启动

### 2.1 前置依赖

需要先准备：

- Conda 环境 `doc_system`；
- Python 3.12；
- Node.js 22.18+（或 24.11+）；
- MySQL 8；
- Redis（只有运行 Document Agent Worker 时必须）。

项目约定在 PowerShell 中执行命令。

### 2.2 创建本地数据库

开发配置默认通过 `DATABASE_URL` 连接 MySQL。数据库不存在时，先执行：

```sql
CREATE DATABASE wind_doc_dev
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
CREATE USER 'wind_doc_user'@'127.0.0.1' IDENTIFIED BY '替换为本地密码';
GRANT ALL PRIVILEGES ON wind_doc_dev.* TO 'wind_doc_user'@'127.0.0.1';
FLUSH PRIVILEGES;
```

### 2.3 启动后端

```powershell
conda activate doc_system
cd D:\vscode程序夹\wind-doc-system
pip install -r .\requirements.txt

Copy-Item .\backend\.env.example .\backend\.env
# 编辑 backend/.env，至少确认 DJANGO_SECRET_KEY、DATABASE_URL、CORS/CSRF 地址

cd .\backend
python manage.py migrate
python manage.py check
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

后端 API 根路径：`http://127.0.0.1:8000/api/v1/`。

如果只需要跑测试，测试设置会使用 `backend/test.sqlite3`，不依赖开发 MySQL：

```powershell
cd D:\vscode程序夹\wind-doc-system\backend
$env:DJANGO_SETTINGS_MODULE = 'config.settings.testing'
pytest
```

### 2.4 启动前端

新开一个 PowerShell：

```powershell
cd D:\vscode程序夹\wind-doc-system\fronted
npm ci
Copy-Item .\.env.example .\.env.local
# 默认值已代理 /api 到 http://127.0.0.1:8000

npm run dev
```

访问：`http://localhost:5174`。

### 2.5 启动 Document Agent Worker（可选）

先确认 Redis 已启动，并在 `backend/.env` 中配置 `REDIS_URL`。再开第三个 PowerShell：

```powershell
conda activate doc_system
cd D:\vscode程序夹\wind-doc-system\backend
python manage.py run_document_generation_worker
```

部署前只验证 Redis 和 Worker 能否启动，可使用：

```powershell
python manage.py run_document_generation_worker --burst
```

`--burst` 处理完当前队列后退出。Worker 会先恢复遗留的生成任务；Windows 使用 RQ `SimpleWorker`，Linux 使用标准 Worker。

## 3. 目录与代码入口

```text
backend/
├─ config/                         Django 配置、根路由、API 路由
├─ apps/
│  ├─ accounts/                    用户、登录、密码、WebAuthn
│  ├─ access/                      文档授权、临时访问
│  ├─ audit/                       审计日志
│  ├─ documents/                   文档、版本、上传、下载
│  ├─ folders/                     文件夹、人员资料
│  ├─ locations/                   定位上报与管理员查询
│  ├─ notifications/               通知
│  ├─ projects/                    项目与项目成员
│  ├─ system/                      健康检查、系统备份
│  └─ document_generation/         Document Agent Django 适配层
├─ common/                         认证、异常、请求 ID 等公共能力
├─ scripts/document_agent/         Agent 离线评测、门禁、Provider 检查
└─ manage.py                       Django 命令入口

fronted/
├─ src/app/                        应用启动、路由、装配
├─ src/layouts/                    全局布局
├─ src/modules/                    按业务模块组织页面、API、Store、组件
├─ src/core/                       HTTP 客户端和基础设施
├─ src/shared/                     公共组件、类型、组合式函数
└─ tests/                          Vitest 单元测试

docs/document_agent/               Document Agent 分阶段门禁和验收资料
deploy/                             发布、回退、Nginx 配置
```

### 后端修改位置

一个业务 App 内的职责约定：

| 文件 | 放什么 |
| --- | --- |
| `models.py` | 字段、关系、约束、索引、简单模型行为 |
| `services.py` | 写操作和完整业务流程 |
| `selectors.py` | 查询逻辑和只读数据获取 |
| `permissions.py` | 权限判断 |
| `serializers.py` | 输入校验和响应序列化 |
| `views.py` | 请求编排，保持轻量 |
| `urls.py` | 当前 App 的 API 路由 |
| `tests/` | API、服务和关键失败路径测试 |

新增或修改数据库结构必须生成 Django Migration，不要直接改已执行过的迁移文件。

### 前端修改位置

优先在对应的 `fronted/src/modules/<业务模块>/` 内修改。跨模块能力放到 `src/core` 或 `src/shared`；主题和全局样式放到 `src/styles`，不要在单个页面复制一套全局 Token。

## 4. 请求与数据流

```text
浏览器 :5174
  └─ Vite 将 /api 代理到 Django :8000
       ├─ MySQL：用户、项目、文档元数据、权限、任务、审计
       ├─ 文件存储：DOCX/PDF 等二进制文件
       └─ Redis/RQ：仅保存异步任务调度信息
             └─ Document Agent Worker
                  ├─ LLM：事实提取、章节生成
                  └─ Embedding：知识章节向量化/检索
```

Document Agent 的核心边界：

- 只生成风电机组检测“四措两案”入场资料初稿；
- 不生成检测报告、检测结论、实测结果或完工资料；
- MySQL 是任务、章节、状态、审核记录的权威来源；
- Redis 不保存正文、Prompt、合同或生成文件；
- 正式导出仍进入当前项目的“技术方案”目录，并复用现有文档权限和下载链路；
- 前端开关只控制页面显示，不能代替后端权限和状态机。

## 5. 配置

### 后端配置

模板：`backend/.env.example`；生产模板：`backend/.env.production.example`。

| 变量 | 作用 |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | 开发用 `config.settings.development`；生产用 `config.settings.production` |
| `DATABASE_URL` | MySQL 连接串 |
| `DJANGO_SECRET_KEY` | Django 密钥；生产必须使用随机长密钥 |
| `DJANGO_ALLOWED_HOSTS` | 允许访问的主机名 |
| `DJANGO_CORS_ALLOWED_ORIGINS` | 前端来源 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | CSRF 信任来源 |
| `FILE_STORAGE_ROOT` | 私有文档文件根目录 |
| `TEMPORARY_STORAGE_ROOT` | 导出和临时文件目录 |
| `LOGIN_REQUIRE_WEBAUTHN` | 是否要求登录时设备验证 |
| `LOCATION_REPORT_REQUIRE_WEBAUTHN` | 是否要求定位上报时设备验证；与登录开关独立 |
| `REDIS_URL` | RQ 队列连接 |
| `DOCUMENT_AGENT_ENABLED` | 后端是否启用 Document Agent |
| `DOCUMENT_AGENT_PHASE5_APPROVED` | 生产启用门禁 |
| `DOCUMENT_AGENT_ALLOW_FAKE_PROVIDER` | Fake Provider；生产必须为 `false` |
| `LLM_*` / `EMBEDDING_*` | 真实模型和向量服务配置，仅通过环境变量提供 |

开发环境默认启用 Django Admin 和 API 文档；生产配置会强制关闭二者。开发 API 文档地址：

```text
http://127.0.0.1:8000/api/docs/
http://127.0.0.1:8000/api/schema/
```

### 前端配置

模板：`fronted/.env.example`，本地文件为 `fronted/.env.local`。

| 变量 | 作用 |
| --- | --- |
| `VITE_API_BASE_URL` | 浏览器使用的 API 前缀，默认 `/api/v1` |
| `VITE_API_PROXY_TARGET` | Vite 开发代理目标，默认 `http://127.0.0.1:8000` |
| `VITE_AMAP_KEY` | 高德地图浏览器端 Key |
| `VITE_AMAP_SECURITY_JS_CODE` | 高德安全密钥 |
| `VITE_DOCUMENT_AGENT_ENABLED` | 是否显示 Agent 页面；不改变后端权限 |

所有 `VITE_*` 变量都会进入浏览器包，不得放服务端密钥、LLM Key、Embedding Key 或数据库密码。

## 6. 常用开发命令

后端命令在 `backend/` 执行：

```powershell
conda activate doc_system
cd D:\vscode程序夹\wind-doc-system\backend

python manage.py check
python manage.py makemigrations --check --dry-run
pytest
ruff check .
ruff format --check .
mypy apps common
```

前端命令在 `fronted/` 执行：

```powershell
cd D:\vscode程序夹\wind-doc-system\fronted

npm run type-check
npm run lint
npm run test:unit
npm run test:e2e
npm run build
```

Document Agent 常用检查：

```powershell
cd D:\vscode程序夹\wind-doc-system\backend

python manage.py check_document_agent_runtime --check-providers
python manage.py recover_document_generation_tasks
```

语料批量预检/执行：

```powershell
python manage.py index_technical_solution_corpus --approved-by <系统管理员用户名>
python manage.py index_technical_solution_corpus --approved-by <系统管理员用户名> --execute
```

具体 Phase 0、4、5、6、7、8 的门禁和评测步骤见 [`docs/document_agent/`](docs/document_agent/)。

## 7. API 入口

统一前缀：`/api/v1/`。主要资源：

- `auth/*`：登录、退出、当前用户、密码、WebAuthn、CSRF；
- `users`：用户管理；
- `projects`、`projects/{id}/members`：项目和成员；
- `folders`、`documents`：目录、文档、版本、上传、下载；
- `document-grants`、`temporary-access-grants`：授权和临时访问；
- `locations/*`：定位挑战、定位上报、本人/管理员查询；
- `notifications`、`audit-logs`：通知和审计；
- `document-generation/*`：模板、知识上传、任务、章节审核、导出；
- `health/`：健康检查。

路由总入口：`backend/config/urls.py`、`backend/config/api_urls.py`。每个 App 的具体路径在对应的 `urls.py`。

## 8. 生产发布

生产发布不要手工复制代码。入口是 [`deploy/publish.ps1`](deploy/publish.ps1)，完整说明见 [`deploy/README.md`](deploy/README.md)。发布前提是服务器已有 Nginx、MySQL、Redis、systemd、Python 3.12、Node.js 22 和 `winddoc` 用户。

首次配置：

```powershell
Copy-Item .\deploy\publish.config.example.json .\deploy\publish.config.local.json
# 只填写 SSH 私钥路径和其他发布参数；不要填写私钥内容或生产密钥
```

正常发布：

```powershell
.\deploy\publish.ps1
```

回退：

```powershell
.\deploy\publish.ps1 -Action Rollback
```

检测到待执行迁移时，发布脚本默认停止并生成迁移计划；审核后才显式使用 `-AllowMigrations`。迁移前会创建系统备份，数据库恢复需要人工确认。

## 9. 常见问题

### 前端打开但 API 全部失败

确认后端监听 `127.0.0.1:8000`，前端 `.env.local` 中 `VITE_API_PROXY_TARGET` 正确，并重启 Vite。

### WebAuthn 报来源或 RP ID 错误

本地统一访问 `http://localhost:5174`，并确认后端 `.env` 中：

```text
WEBAUTHN_RP_ID=localhost
WEBAUTHN_ALLOWED_ORIGINS=http://localhost:5174
```

不要在 `localhost` 和 `127.0.0.1` 之间混用。

### 后端启动提示 DATABASE_URL 必须是 MySQL

开发设置会拒绝非测试环境的 SQLite。检查 `backend/.env` 中 `DATABASE_URL` 是否为 MySQL 连接串；只有 `config.settings.testing` 使用 SQLite。

### Document Agent 页面不显示

同时检查前端 `VITE_DOCUMENT_AGENT_ENABLED=true`、后端 `DOCUMENT_AGENT_ENABLED=true`，以及后端是否满足 Phase 5 门禁。生产还必须配置真实 HTTPS LLM/Embedding 服务，不能启用 Fake Provider。

### 生成任务一直排队

确认 Redis 可连接、Worker 已启动，并执行：

```powershell
python manage.py recover_document_generation_tasks
python manage.py run_document_generation_worker --burst
```

## 10. 安全与修改边界

- 不提交 `.env`、私钥、密码、Token、模型密钥或生产配置。
- 不把文件二进制写入 MySQL，不直接公开文件系统目录。
- 不用前端隐藏按钮实现权限控制；后端 Permission、Service 和下载链路必须同步修改。
- 不直接编辑已执行迁移，不用 `save()`、Signal 或 View 承载复杂业务流程。
- 保留与当前任务无关的工作区修改，不执行未经授权的重置、回退或大规模重构。
