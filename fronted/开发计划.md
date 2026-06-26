# 风电资料系统前端 API 对齐开发计划

## Summary

- 在 `D:\vscode程序夹\wind-doc-system\fronted` 下建设一套 Vue 3 + TypeScript + Vite + Vue Router + Pinia + Element Plus 前端应用。
- 页面结构以 `fronted\前端信息架构与完整目录.md` 为蓝本，但以 `backend/docs/openapi.yaml`、`frontend_handoff.md` 和后端代码中的真实 API 为最终约束。
- 核心原则：资料中心是主工作区；公共资料和项目资料复用同一个 `DocumentExplorer`；权限菜单只控制前端体验，实际数据范围和操作权限由后端接口返回和 403/404/409 结果决定。
- 当前后端未提供的能力不做假实现：系统配置、备份恢复、全局统计、最近访问、标记全部通知已读等先隐藏或做“后端未开放”占位，不进入首轮核心交付。

## Key Changes

- 工程基线：
  - 建立 `fronted` 前端工程，配置 Vite、Vue Router、Pinia、Element Plus、Axios、Vitest、Playwright、路径别名和环境变量。
  - API 前缀使用 `/api/v1/`，本地开发通过 Vite proxy 转发到 Django。
  - Axios 全局启用 `withCredentials: true`，写请求统一注入 `X-CSRFToken`。

- 认证与主框架：
  - 实现 `GET /auth/csrf/`、`POST /auth/login/`、`GET /auth/me/`、`POST /auth/logout/`、`POST /auth/change-password/`。
  - 登录后进入主框架；未登录访问业务路由跳转登录；`must_change_password` 用户进入改密流程。
  - 主菜单按 `user.role` 生成，按钮按角色、项目成员能力和接口返回状态共同控制。

- 资料中心：
  - 实现统一 `DocumentExplorer`，支持 `all/public/project/mine/shared-with-me/recycle-bin` 这些前端上下文。
  - 文件夹树调用 `GET /folders/tree/?project_id=<id>`；公共资料不传 `project_id`。
  - 文档列表调用 `GET /documents/`，使用后端分页、`search`、`ordering`、`project`、`folder`、`access_level`。
  - 文件操作覆盖上传、新版本、下载、批量下载、编辑、移动、软删除、恢复、永久删除；编辑/移动/删除/恢复/永久删除必须携带详情中的 `updated_at` 作为 `expected_updated_at`，409 时刷新详情并提示用户重试。

- 项目与授权：
  - 项目页实现项目列表、创建、编辑、归档、取消归档；项目成员放在项目详情内，调用 `/projects/{project_pk}/members/`。
  - 项目资料页复用 `DocumentExplorer` 并传入 `projectId`。
  - 内部授权只针对 `restricted` 文档，调用 `/document-grants/`，支持查询、创建、更新、撤销。
  - 临时授权调用 `/temporary-access-grants/`；创建响应中的 `token/download_url` 只展示一次，前端必须提供复制入口。

- 用户、审计、通知和临时访问：
  - 用户管理仅系统管理员可见，覆盖用户 CRUD、停用、重置密码。
  - 审计中心仅按当前后端能力做系统管理员全局日志页，支持 `user/action/resource_type/resource_id/result/search/ordering`。
  - 通知放在顶部抽屉或轻量页面，支持列表、未读筛选、单条已读/未读；不实现“全部已读”。
  - `/share/:token` 使用空白布局，只触发 `/temporary-access/{token}/download/`，不进入主框架，不显示搜索、目录树或用户信息。

## Public Interfaces And Types

- 统一封装 `core/http`：
  - `ApiPage<T> = { count; next; previous; results }`
  - `ApiError = { status; detail?; fieldErrors?; requestId? }`
  - 下载接口按 blob 处理，并解析 `Content-Disposition` 文件名。

- 业务类型按后端字段建模：
  - `User`: `id, username, real_name, employee_no, role, phone, email, is_active, must_change_password, created_at`
  - `Project`: `id, name, code, description, manager, manager_name, status, created_at, updated_at, archived_at`
  - `ProjectMember`: `role, can_upload, can_download_restricted, can_manage_folder, can_delete, can_restore, can_manage_permission`
  - `Folder`: `id, project, parent, name, code, sort_order, is_active, is_system_root`
  - `Document`: `id, project, folder, title, description, access_level, current_version, lock_version, deleted_at, created_at, updated_at`
  - `DocumentGrant` 和 `TemporaryAccessGrant` 保留后端的 `is_active/is_expired/remaining_downloads/revoked_at` 状态字段。

## Test Plan

- 单元测试：
  - CSRF 注入、401/403/404/409/413 错误归一化、分页参数、blob 下载文件名解析。
  - 权限菜单生成、项目成员能力转按钮状态、`expected_updated_at` 写请求构造。
  - 临时授权 token 只在创建结果中展示的状态逻辑。

- 组件测试：
  - 登录表单、主框架菜单、通知抽屉、文件夹树、文档表格、上传/移动/授权弹窗。
  - 回收站恢复、永久删除确认、批量下载最多 20 个的前端预校验。

- E2E：
  - 使用种子账号 `admin/manager/operator/viewer` 验证不同菜单和数据范围。
  - 跑通登录、项目资料浏览、上传、搜索、下载、新版本、删除恢复、内部授权、临时下载。
  - 验证无权限按钮隐藏和接口 403 后的页面提示。

## Assumptions

- 前端工程目录使用现有仓库拼写 `fronted`，不额外改名为 `frontend`。
- 首轮开发严格围绕当前后端已开放 API；没有后端接口的页面不做模拟业务数据。
- 文件预校验使用后端允许类型：`.pdf/.doc/.docx/.xls/.xlsx/.jpg/.jpeg/.png`，大小默认按 200MB 提示，但以后端 413 为准。
- 审计页当前只对系统管理员开放；项目范围审计若后端未来补接口再扩展。
