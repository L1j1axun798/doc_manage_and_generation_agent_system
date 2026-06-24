# 里程碑 5 说明

本阶段新增 `Document.access_level`，支持 `internal` 和 `restricted` 两种基础访问级别。文档列表、详情和当前版本下载都通过后端权限判断；受限文档仅系统管理员或具备 `can_download_restricted` 的项目成员可见和下载。下载当前版本时只返回文件流，不暴露真实物理路径，并记录成功、拒绝或存储缺失审计。
