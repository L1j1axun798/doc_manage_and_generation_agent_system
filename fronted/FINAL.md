# 风电资料系统
# 最优前端信息架构与完整目录

> 目标：构建一套面向公司真实办公场景的文件管理前端。  
> 原则：文件优先、模块独立、权限驱动、统一复用、避免重复页面。  
> 推荐技术栈：Vue 3 + TypeScript + Vite + Vue Router + Pinia + Element Plus + Axios + Vitest + Playwright。

---

# 一、总体结论

不建议为系统管理员、项目经理、资料整理员分别建立三套前端工程。

正确方案是：

```text
一套 Vue 前端应用
    ├── 根据权限生成主菜单
    ├── 根据权限控制页面操作
    ├── 根据后端数据范围显示数据
    └── 临时用户使用独立轻量页面
```

四种身份的差异主要体现在：

```text
可见菜单不同
可进入页面不同
可执行按钮不同
可查询数据范围不同
```

临时用户例外。临时用户不进入主框架，只访问指定的临时下载页面。

---

# 二、前端设计原则

## 1. 文件管理是系统主轴

前端核心模块是：

```text
资料中心
```

项目、用户、授权、审计和系统管理，都是围绕资料管理提供的辅助能力。

## 2. 公共资料与项目资料共用文件工作区

公共资料和项目资料底层都属于文件管理能力。

必须复用同一套：

```text
文件夹树
文件列表
文件详情
文件上传
文件下载
文件版本
文件移动
文件删除
文件恢复
权限展示
```

项目资料不能重新开发一套独立文件页面。

## 3. 固有根目录由后端驱动

以下目录不能硬编码成独立 Vue 页面：

```text
完工资料档案
公司资质
人员资质
工器具年检资质
劳动防护用品
仪器设备年检资质
车辆年检及资质
其他资料
```

前端应从文件夹树 API 获取目录，根据权限渲染。

## 4. 菜单权限不等于安全权限

前端可以隐藏无权限菜单和按钮，但后端必须再次判断权限。

## 5. 模块间保持单向依赖

推荐依赖方向：

```text
app
  ↓
modules
  ↓
core / shared
```

禁止：

```text
shared 反向依赖业务模块
documents 与 projects 循环依赖
页面直接访问 Axios
```

---

# 三、最终一级信息架构

```text
登录
  ↓
主框架
  ├── 首页
  ├── 资料中心
  ├── 项目管理
  ├── 授权管理
  ├── 用户管理
  ├── 审计中心
  └── 系统管理
```

顶部栏：

```text
全局搜索
通知中心
当前用户
修改密码
退出登录
```

临时访问：

```text
临时下载页面
```

临时下载页面不进入主框架。

---

# 四、完整页面结构

## 1. 公共页面

```text
登录
403 无权限
404 页面不存在
500 系统异常
临时下载
```

## 2. 首页

```text
首页
├── 快捷操作
│   ├── 上传资料
│   ├── 进入资料中心
│   ├── 进入我的项目
│   └── 创建临时授权
├── 我的工作
│   ├── 最近访问
│   ├── 最近上传
│   ├── 我的资料
│   ├── 已授权给我
│   └── 我的项目
├── 提醒
│   ├── 未读通知
│   ├── 新版本提醒
│   └── 临时授权到期提醒
└── 系统概况
    ├── 文件总数
    ├── 本月新增
    ├── 存储使用量
    └── 活跃用户
```

首页内容根据身份调整。

## 3. 资料中心

```text
资料中心
├── 全部资料
├── 固有根目录
│   ├── 完工资料档案
│   ├── 公司资质
│   ├── 人员资质
│   ├── 工器具年检资质
│   ├── 劳动防护用品
│   ├── 仪器设备年检资质
│   ├── 车辆年检及资质
│   └── 其他资料
├── 我的资料
├── 已授权给我
└── 回收站
```

固有根目录由后端动态返回，不建立八个重复页面。

资料中心统一使用：

```text
DocumentExplorer
├── FolderTree
├── DocumentToolbar
├── DocumentSearchPanel
├── DocumentTable
├── DocumentDetailDrawer
├── DocumentUploadDialog
├── DocumentVersionPanel
├── DocumentPermissionPanel
└── DocumentOperationLog
```

## 4. 项目管理

```text
项目管理
└── 项目列表
    └── 项目详情
        ├── 项目概况
        ├── 项目成员
        ├── 项目资料
        └── 归档信息
```

项目资料复用 `DocumentExplorer`，传入 `projectId` 和项目范围。

项目成员必须位于项目详情内，不能作为脱离项目上下文的普通页面。

## 5. 授权管理

```text
授权管理
├── 内部文件授权
└── 临时访问授权
```

文件详情中也应提供局部授权入口。

全局授权管理用于：

```text
查询所有授权
查看授权对象
查看授权创建人
查看到期时间
撤销授权
查看临时下载次数
```

## 6. 用户管理

```text
用户管理
├── 用户列表
├── 用户详情
├── 创建用户
├── 修改用户
├── 停用用户
└── 重置密码
```

不提供公开注册页面。

## 7. 审计中心

第一版使用一个统一日志页面。

```text
审计中心
└── 审计日志
    ├── 全部事件
    ├── 登录事件
    ├── 文件操作
    ├── 下载事件
    ├── 权限变更
    └── 系统事件
```

以上分类建议通过 Tab 或筛选条件实现，不开发多个重复表格页面。

## 8. 系统管理

```text
系统管理
├── 资料目录配置
├── 系统配置
├── 备份与恢复
└── 系统状态
```

`资料目录配置` 管理：

```text
固有根目录
根目录顺序
目录启用状态
项目默认目录模板
```

它不同于资料中心中的普通文件夹操作。

## 9. 通知中心

通知入口放在顶部栏，不放入系统管理菜单。

```text
通知中心
├── 未读通知
├── 全部通知
└── 标记全部已读
```

---

# 五、不同身份的前端结构

## 1. 系统管理员

```text
首页
资料中心
├── 全部资料
├── 固有根目录
├── 我的资料
├── 已授权给我
└── 回收站

项目管理
├── 全部项目
├── 进行中项目
└── 已归档项目

授权管理
├── 内部文件授权
└── 临时访问授权

用户管理
审计中心
系统管理
```

管理员首页建议显示：

```text
文件总量
存储使用量
用户数量
最近异常操作
备份状态
系统状态
```

管理员可见操作：

```text
创建和停用用户
管理公共目录
管理全部项目
管理全部文件权限
查看全部审计日志
执行备份恢复
查看系统状态
永久删除文件
```

## 2. 项目经理

```text
首页
资料中心
├── 全部可见资料
├── 固有根目录
├── 我的资料
├── 已授权给我
└── 回收站

项目管理
├── 我负责的项目
├── 我参与的项目
└── 已归档项目

授权管理
├── 项目内文件授权
└── 临时访问授权

审计中心
└── 项目范围日志
```

项目经理不显示：

```text
用户管理
系统管理
全局审计
全局目录配置
```

项目经理是否可以创建临时授权，应以后端项目权限为准。

## 3. 资料整理员

```text
首页
资料中心
├── 全部可见资料
├── 固有根目录
├── 我的资料
├── 已授权给我
└── 回收站

项目管理
├── 我参与的项目
└── 项目资料
```

通常不显示：

```text
授权管理
用户管理
系统管理
全局审计中心
项目成员管理
```

如果后端授予某个具体项目的授权管理权限，可以在文件详情中显示授权按钮，但不一定开放全局授权管理页面。

## 4. 临时用户

临时用户不进入主框架，不加载主菜单，不访问资料中心。

访问方式：

```text
/share/:token
```

页面结构：

```text
临时资料访问
├── 文件名称
├── 文件版本
├── 文件大小
├── 授权创建人
├── 授权有效期
├── 剩余下载次数
├── 下载按钮
└── 失效或错误提示
```

临时页面状态：

```text
有效
已过期
已撤销
下载次数已用完
Token 无效
文件不存在
下载失败
```

临时访问页面不显示：

```text
文件搜索
其他文件
项目结构
用户信息
主导航
系统通知
```

---

# 六、角色菜单矩阵

| 模块 | 管理员 | 项目经理 | 资料整理员 | 临时用户 |
|---|---:|---:|---:|---:|
| 首页 | 是 | 是 | 是 | 否 |
| 资料中心 | 全部 | 授权范围 | 授权范围 | 否 |
| 项目管理 | 全部 | 负责/参与 | 参与 | 否 |
| 项目成员 | 全部 | 负责项目 | 否 | 否 |
| 授权管理 | 全部 | 项目范围 | 通常否 | 否 |
| 用户管理 | 是 | 否 | 否 | 否 |
| 审计中心 | 全部 | 项目范围 | 可选本人记录 | 否 |
| 系统管理 | 是 | 否 | 否 | 否 |
| 回收站 | 全部 | 项目范围 | 本人/授权范围 | 否 |
| 临时下载页 | 可测试 | 可测试 | 可测试 | 是 |

菜单仅控制显示。数据范围必须由后端接口保证。

---

# 七、推荐路由结构

## 1. 公共路由

```text
/login
/share/:token
/403
/404
/500
```

## 2. 主框架路由

```text
/dashboard

/documents
/documents/folders/:folderId
/documents/mine
/documents/shared-with-me
/documents/recycle-bin
/documents/:documentId

/projects
/projects/:projectId
/projects/:projectId/overview
/projects/:projectId/members
/projects/:projectId/documents
/projects/:projectId/archive

/access/internal
/access/temporary

/users
/users/create
/users/:userId

/audit

/system/directories
/system/settings
/system/backup
/system/status
```

## 3. 通知

通知可以使用抽屉，不必建立独立一级页面。

可选路由：

```text
/notifications
```

---

# 八、路由权限设计

路由使用 `meta` 描述基本权限：

```ts
interface AppRouteMeta {
  title: string
  requiresAuth?: boolean
  permission?: string
  roles?: string[]
  hideInMenu?: boolean
  activeMenu?: string
  layout?: 'main' | 'public' | 'blank'
}
```

示例：

```ts
{
  path: '/users',
  component: () => import('./pages/UserListPage.vue'),
  meta: {
    title: '用户管理',
    requiresAuth: true,
    permission: 'user.view',
    roles: ['system_admin']
  }
}
```

路由 `meta` 只负责前端访问体验，后端仍必须执行权限判断。

项目内权限不能全部写入静态路由。进入项目详情后，应从后端读取当前用户在该项目中的能力。

---

# 九、完整前端工程目录

```text
frontend/
├── .env
├── .env.development
├── .env.production
├── .env.example
├── .gitignore
├── index.html
├── package.json
├── package-lock.json
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── vite.config.ts
├── vitest.config.ts
├── playwright.config.ts
├── eslint.config.js
├── README.md
├── AGENTS.md
│
├── public/
│   ├── favicon.ico
│   └── static/
│
├── src/
│   ├── app/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   ├── bootstrap.ts
│   │   └── register-element-plus.ts
│   │
│   ├── config/
│   │   ├── env.ts
│   │   ├── app.ts
│   │   ├── constants.ts
│   │   └── feature-flags.ts
│   │
│   ├── core/
│   │   ├── http/
│   │   │   ├── client.ts
│   │   │   ├── interceptors.ts
│   │   │   ├── error-normalizer.ts
│   │   │   ├── csrf.ts
│   │   │   └── download.ts
│   │   ├── auth/
│   │   │   ├── session.ts
│   │   │   ├── auth-guard.ts
│   │   │   └── auth.types.ts
│   │   ├── permissions/
│   │   │   ├── can.ts
│   │   │   ├── permission.types.ts
│   │   │   ├── permission.directive.ts
│   │   │   └── project-capabilities.ts
│   │   ├── router/
│   │   │   ├── index.ts
│   │   │   ├── guards.ts
│   │   │   ├── route-meta.d.ts
│   │   │   └── menu-builder.ts
│   │   ├── errors/
│   │   │   ├── app-error.ts
│   │   │   ├── error-codes.ts
│   │   │   └── error-handler.ts
│   │   └── storage/
│   │       ├── keys.ts
│   │       └── preferences.ts
│   │
│   ├── layouts/
│   │   ├── MainLayout.vue
│   │   ├── PublicLayout.vue
│   │   ├── BlankLayout.vue
│   │   └── components/
│   │       ├── AppSidebar.vue
│   │       ├── AppHeader.vue
│   │       ├── AppBreadcrumb.vue
│   │       ├── AppUserMenu.vue
│   │       ├── AppNotificationBell.vue
│   │       └── AppContent.vue
│   │
│   ├── modules/
│   │   ├── auth/
│   │   │   ├── api/auth.api.ts
│   │   │   ├── components/
│   │   │   │   ├── LoginForm.vue
│   │   │   │   └── ChangePasswordForm.vue
│   │   │   ├── pages/
│   │   │   │   ├── LoginPage.vue
│   │   │   │   └── ChangePasswordPage.vue
│   │   │   ├── stores/auth.store.ts
│   │   │   ├── auth.types.ts
│   │   │   ├── routes.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── dashboard/
│   │   │   ├── api/dashboard.api.ts
│   │   │   ├── components/
│   │   │   │   ├── QuickActions.vue
│   │   │   │   ├── RecentDocuments.vue
│   │   │   │   ├── MyProjects.vue
│   │   │   │   ├── DashboardMetrics.vue
│   │   │   │   └── ReminderPanel.vue
│   │   │   ├── pages/DashboardPage.vue
│   │   │   ├── dashboard.types.ts
│   │   │   ├── routes.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── documents/
│   │   │   ├── api/
│   │   │   │   ├── documents.api.ts
│   │   │   │   ├── folders.api.ts
│   │   │   │   └── versions.api.ts
│   │   │   ├── components/
│   │   │   │   ├── DocumentExplorer.vue
│   │   │   │   ├── DocumentWorkspace.vue
│   │   │   │   ├── FolderTree.vue
│   │   │   │   ├── FolderTreeNode.vue
│   │   │   │   ├── DocumentToolbar.vue
│   │   │   │   ├── DocumentSearchPanel.vue
│   │   │   │   ├── DocumentTable.vue
│   │   │   │   ├── DocumentTableActions.vue
│   │   │   │   ├── DocumentDetailDrawer.vue
│   │   │   │   ├── DocumentUploadDialog.vue
│   │   │   │   ├── DocumentEditDialog.vue
│   │   │   │   ├── DocumentMoveDialog.vue
│   │   │   │   ├── DocumentVersionPanel.vue
│   │   │   │   ├── DocumentVersionUploadDialog.vue
│   │   │   │   ├── DocumentPermissionPanel.vue
│   │   │   │   ├── FolderCreateDialog.vue
│   │   │   │   ├── FolderEditDialog.vue
│   │   │   │   ├── FolderMoveDialog.vue
│   │   │   │   ├── FileTypeIcon.vue
│   │   │   │   ├── AccessLevelTag.vue
│   │   │   │   └── UploadProgressItem.vue
│   │   │   ├── composables/
│   │   │   │   ├── useDocumentExplorer.ts
│   │   │   │   ├── useDocumentActions.ts
│   │   │   │   ├── useDocumentQuery.ts
│   │   │   │   ├── useFolderTree.ts
│   │   │   │   ├── useFileUpload.ts
│   │   │   │   └── useDocumentDownload.ts
│   │   │   ├── pages/
│   │   │   │   ├── DocumentCenterPage.vue
│   │   │   │   ├── DocumentDetailPage.vue
│   │   │   │   ├── MyDocumentsPage.vue
│   │   │   │   ├── SharedWithMePage.vue
│   │   │   │   └── RecycleBinPage.vue
│   │   │   ├── stores/document-preferences.store.ts
│   │   │   ├── documents.types.ts
│   │   │   ├── documents.permissions.ts
│   │   │   ├── routes.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── projects/
│   │   │   ├── api/
│   │   │   │   ├── projects.api.ts
│   │   │   │   └── project-members.api.ts
│   │   │   ├── components/
│   │   │   │   ├── ProjectTable.vue
│   │   │   │   ├── ProjectFormDialog.vue
│   │   │   │   ├── ProjectStatusTag.vue
│   │   │   │   ├── ProjectOverview.vue
│   │   │   │   ├── ProjectMemberTable.vue
│   │   │   │   ├── ProjectMemberDialog.vue
│   │   │   │   ├── ProjectDocumentWorkspace.vue
│   │   │   │   └── ProjectArchivePanel.vue
│   │   │   ├── composables/
│   │   │   │   ├── useProjects.ts
│   │   │   │   ├── useProjectDetail.ts
│   │   │   │   └── useProjectCapabilities.ts
│   │   │   ├── layouts/ProjectDetailLayout.vue
│   │   │   ├── pages/
│   │   │   │   ├── ProjectListPage.vue
│   │   │   │   ├── ProjectDetailPage.vue
│   │   │   │   ├── ProjectOverviewPage.vue
│   │   │   │   ├── ProjectMembersPage.vue
│   │   │   │   ├── ProjectDocumentsPage.vue
│   │   │   │   └── ProjectArchivePage.vue
│   │   │   ├── projects.types.ts
│   │   │   ├── projects.permissions.ts
│   │   │   ├── routes.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── access/
│   │   │   ├── api/
│   │   │   │   ├── internal-grants.api.ts
│   │   │   │   └── temporary-grants.api.ts
│   │   │   ├── components/
│   │   │   │   ├── InternalGrantTable.vue
│   │   │   │   ├── InternalGrantDialog.vue
│   │   │   │   ├── TemporaryGrantTable.vue
│   │   │   │   ├── TemporaryGrantDialog.vue
│   │   │   │   ├── GrantStatusTag.vue
│   │   │   │   └── TemporaryLinkResult.vue
│   │   │   ├── composables/
│   │   │   │   ├── useInternalGrants.ts
│   │   │   │   └── useTemporaryGrants.ts
│   │   │   ├── pages/
│   │   │   │   ├── InternalGrantPage.vue
│   │   │   │   └── TemporaryGrantPage.vue
│   │   │   ├── access.types.ts
│   │   │   ├── access.permissions.ts
│   │   │   ├── routes.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── users/
│   │   │   ├── api/users.api.ts
│   │   │   ├── components/
│   │   │   │   ├── UserTable.vue
│   │   │   │   ├── UserFormDialog.vue
│   │   │   │   ├── UserStatusTag.vue
│   │   │   │   ├── UserRoleTag.vue
│   │   │   │   └── ResetPasswordDialog.vue
│   │   │   ├── composables/useUsers.ts
│   │   │   ├── pages/
│   │   │   │   ├── UserListPage.vue
│   │   │   │   ├── UserCreatePage.vue
│   │   │   │   └── UserDetailPage.vue
│   │   │   ├── users.types.ts
│   │   │   ├── users.permissions.ts
│   │   │   ├── routes.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── audit/
│   │   │   ├── api/audit.api.ts
│   │   │   ├── components/
│   │   │   │   ├── AuditFilterBar.vue
│   │   │   │   ├── AuditTable.vue
│   │   │   │   ├── AuditDetailDrawer.vue
│   │   │   │   └── AuditResultTag.vue
│   │   │   ├── composables/useAuditLogs.ts
│   │   │   ├── pages/AuditLogPage.vue
│   │   │   ├── audit.types.ts
│   │   │   ├── audit.permissions.ts
│   │   │   ├── routes.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── notifications/
│   │   │   ├── api/notifications.api.ts
│   │   │   ├── components/
│   │   │   │   ├── NotificationDrawer.vue
│   │   │   │   ├── NotificationList.vue
│   │   │   │   └── NotificationItem.vue
│   │   │   ├── stores/notification.store.ts
│   │   │   ├── notifications.types.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── system/
│   │   │   ├── api/
│   │   │   │   ├── system.api.ts
│   │   │   │   ├── directory-config.api.ts
│   │   │   │   └── backup.api.ts
│   │   │   ├── components/
│   │   │   │   ├── DirectoryConfigTree.vue
│   │   │   │   ├── SystemSettingsForm.vue
│   │   │   │   ├── BackupHistoryTable.vue
│   │   │   │   ├── BackupActionPanel.vue
│   │   │   │   ├── SystemHealthCards.vue
│   │   │   │   └── StorageUsagePanel.vue
│   │   │   ├── pages/
│   │   │   │   ├── DirectoryConfigPage.vue
│   │   │   │   ├── SystemSettingsPage.vue
│   │   │   │   ├── BackupManagementPage.vue
│   │   │   │   └── SystemStatusPage.vue
│   │   │   ├── system.types.ts
│   │   │   ├── system.permissions.ts
│   │   │   ├── routes.ts
│   │   │   └── index.ts
│   │   │
│   │   └── public-share/
│   │       ├── api/public-share.api.ts
│   │       ├── components/
│   │       │   ├── SharedFileCard.vue
│   │       │   ├── ShareStatusPanel.vue
│   │       │   └── ShareDownloadButton.vue
│   │       ├── pages/PublicSharePage.vue
│   │       ├── public-share.types.ts
│   │       ├── routes.ts
│   │       └── index.ts
│   │
│   ├── shared/
│   │   ├── components/
│   │   │   ├── AppPageHeader.vue
│   │   │   ├── AppTable.vue
│   │   │   ├── AppPagination.vue
│   │   │   ├── AppEmptyState.vue
│   │   │   ├── AppErrorState.vue
│   │   │   ├── AppLoading.vue
│   │   │   ├── AppConfirmDialog.vue
│   │   │   ├── AppPermissionDenied.vue
│   │   │   ├── AppSearchInput.vue
│   │   │   └── AppStatusTag.vue
│   │   ├── composables/
│   │   │   ├── useAsyncState.ts
│   │   │   ├── usePagination.ts
│   │   │   ├── useDebounce.ts
│   │   │   ├── useTableSelection.ts
│   │   │   └── useConfirm.ts
│   │   ├── directives/permission.ts
│   │   ├── types/
│   │   │   ├── api.types.ts
│   │   │   ├── pagination.types.ts
│   │   │   ├── option.types.ts
│   │   │   └── common.types.ts
│   │   ├── utils/
│   │   │   ├── date.ts
│   │   │   ├── file.ts
│   │   │   ├── format.ts
│   │   │   ├── download.ts
│   │   │   └── validation.ts
│   │   └── constants/
│   │       ├── roles.ts
│   │       ├── permissions.ts
│   │       ├── file-types.ts
│   │       └── routes.ts
│   │
│   ├── styles/
│   │   ├── index.scss
│   │   ├── variables.scss
│   │   ├── reset.scss
│   │   ├── element-plus.scss
│   │   ├── utilities.scss
│   │   └── themes/
│   │       ├── light.scss
│   │       └── dark.scss
│   │
│   ├── assets/
│   │   ├── images/
│   │   ├── icons/
│   │   └── fonts/
│   │
│   └── env.d.ts
│
├── tests/
│   ├── setup.ts
│   ├── unit/
│   │   ├── core/
│   │   ├── documents/
│   │   ├── projects/
│   │   ├── access/
│   │   └── users/
│   └── fixtures/
│       ├── users.ts
│       ├── projects.ts
│       ├── folders.ts
│       └── documents.ts
│
├── e2e/
│   ├── auth.spec.ts
│   ├── document-center.spec.ts
│   ├── project-documents.spec.ts
│   ├── permissions.spec.ts
│   ├── temporary-share.spec.ts
│   └── recycle-bin.spec.ts
│
└── docs/
    ├── frontend-architecture.md
    ├── page-map.md
    ├── permission-ui-matrix.md
    ├── api-integration.md
    ├── design-system.md
    └── frontend-development-plan.md
```

---

# 十、模块公开接口

为了降低模块耦合，每个模块使用 `index.ts` 暴露有限内容。

例如：

```ts
// modules/documents/index.ts
export { default as DocumentExplorer } from './components/DocumentExplorer.vue'
export type {
  Document,
  DocumentExplorerContext
} from './documents.types'
```

项目模块只通过公开入口使用：

```ts
import {
  DocumentExplorer
} from '@/modules/documents'
```

不要直接访问模块内部私有文件。

---

# 十一、模块依赖关系

推荐：

```text
auth
  └── core/http

dashboard
  ├── documents
  ├── projects
  └── notifications

documents
  ├── core/http
  ├── core/permissions
  └── shared

projects
  ├── documents 的公开接口
  ├── core/http
  └── shared

access
  ├── documents 类型
  ├── core/http
  └── shared

users / audit / system / public-share
  ├── core/http
  └── shared
```

禁止：

```text
documents 依赖 projects 页面
shared 依赖任何业务模块
core 依赖 modules
```

---

# 十二、资料中心组件上下文

统一文件工作区建议接收：

```ts
export interface DocumentExplorerContext {
  scope:
    | 'all'
    | 'public'
    | 'project'
    | 'mine'
    | 'shared-with-me'
    | 'recycle-bin'

  projectId?: number
  initialFolderId?: number
  readonly?: boolean
}
```

公共资料：

```vue
<DocumentExplorer scope="public" />
```

项目资料：

```vue
<DocumentExplorer
  scope="project"
  :project-id="projectId"
/>
```

回收站：

```vue
<DocumentExplorer scope="recycle-bin" />
```

---

# 十三、前端权限建议

不要只判断：

```ts
user.role === 'system_admin'
```

优先使用权限能力：

```ts
can('document.upload')
can('document.download')
can('project.manage_member')
can('system.backup')
```

角色用于菜单的大范围筛选，具体按钮使用权限代码。

项目内权限单独读取：

```ts
projectCapabilities.canUpload
projectCapabilities.canManageFolder
projectCapabilities.canDelete
projectCapabilities.canRestore
projectCapabilities.canManagePermission
```

---

# 十四、前端开发顺序

## 里程碑 0：工程基线

```text
Vue 3
TypeScript
Vite
Router
Pinia
Element Plus
Axios
Vitest
Playwright
环境变量
目录结构
```

## 里程碑 1：认证与主框架

```text
登录
CSRF
Session
当前用户
退出
路由守卫
权限菜单
主布局
错误页面
```

## 里程碑 2：资料中心

```text
文件夹树
文件列表
搜索
筛选
分页
文件详情
```

## 里程碑 3：文件操作

```text
上传
下载
修改
移动
版本
删除
恢复
```

## 里程碑 4：项目管理

```text
项目列表
项目详情
项目成员
项目资料
项目归档
```

## 里程碑 5：授权管理

```text
内部授权
临时授权
文件详情授权
临时下载页面
```

## 里程碑 6：用户、审计和通知

```text
用户管理
审计日志
通知中心
```

## 里程碑 7：系统管理

```text
目录配置
系统配置
备份恢复
系统状态
```

## 里程碑 8：测试与部署

```text
单元测试
组件测试
端到端测试
构建检查
Nginx 部署
后端联调回归
```

---

# 十五、最终推荐

最优前端方案是：

```text
一套主前端应用
+
一个临时访问页面
+
按业务域拆分模块
+
按权限动态生成菜单
+
公共资料与项目资料复用 DocumentExplorer
+
后端负责最终权限和数据范围
```

最终一级菜单：

```text
首页
资料中心
项目管理
授权管理
用户管理
审计中心
系统管理
```

但每个身份只能看到其需要的模块。

资料中心必须是默认核心工作区，项目管理、授权、用户、审计和系统管理作为独立治理模块存在。
