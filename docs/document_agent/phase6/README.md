# Document Agent Phase 6

Phase 6 已把入场四措两案能力作为独立 Django App 接入现有系统，且没有修改现有文档核心
表结构。新增模型只关联现有 `Project`、`DocumentVersion`、用户和审计日志。

已实现：

- 模板、批准条款、知识章节、生成任务、来源、生成章节和审核记录模型及迁移；
- ORM 版知识库、条款库和章节存储；
- `/api/v1/document-generation/` 下的任务、来源、事实确认、章节审核、批准和导出接口；
- 项目成员隔离、临时用户拒绝、归档项目拒绝和非法状态跳转；
- 创建、入队和导出幂等；
- 来源只能选择当前用户有权查看的已有项目文档；
- 报告模板、检测报告、完工/竣工及归档语义来源由后端拒绝；
- 正式导出只进入当前项目“技术方案”目录，并继续经过现有文档下载权限；
- 所有写操作写入现有审计日志；
- `bootstrap_document_agent` 对3个批准模板、16个批准条款和真实Embedding知识索引执行
  完整性校验、文件SHA-256校验及幂等导入，支持 `--dry-run`；
- `check_document_agent_runtime` 在启用前检查模板、条款、RAG模型/维度、Redis，并可用
  `--check-providers` 发起不含项目事实的真实模型连通检查；
- 架构门禁保证纯引擎不依赖Django、DRF、RQ、Redis或平台模块，项目详情页只挂载独立
  Document Agent面板。

本地开发库已经完成迁移，并验证初始化命令连续执行两次不会产生重复记录。换服务器时必须
重新运行初始化命令；Phase 5私有盲测输入不迁移到生产系统。

功能开关默认关闭。`DOCUMENT_AGENT_ENABLED=true` 仍不足以启用接口，还必须显式设置
`DOCUMENT_AGENT_PHASE5_APPROVED=true`。在 Phase 5 真实模型和技术负责人验收完成前，
生产环境不得设置这两个值。
