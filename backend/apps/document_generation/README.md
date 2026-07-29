# Document Generation Module

本模块一期只生成“风电机组检测四措两案”入场资料初稿，不生成检测报告、检测结论、实测
结果或完工资料。

模块边界如下：

- `engine/` 是纯业务内核，只依赖标准库和文档/数据处理库，不依赖 Django、DRF、RQ、
  Redis、数据库或平台前端。
- `providers/` 只实现模型与向量接口适配，不读写平台数据库。
- `models.py`、`repositories.py`、`services.py` 和 `selectors.py` 是 Django/MySQL 适配层。
- `queues.py` 只向 Redis 投递 `GenerationTask` UUID；文件、事实和正文始终以 MySQL及受控
  文件存储为准。
- `jobs.py` 负责把平台对象组装成纯内核契约，正式路径必须使用
  `ControlledSectionValidator`。
- `workflow_events.py` 把纯内核 Trace 转成可审计的数据库事件；只记录业务阶段、Tool
  Use、模型/RAG状态和脱敏统计，不记录模型内部思维链或提示词正文。
- `bootstrap.py` 负责把批准的模板、条款和RAG索引幂等导入平台；管理命令只是薄入口。
- 前端功能完整封装在 `fronted/src/modules/document-generation/`，项目详情页只挂载一个
  面板并由功能开关隔离。

`scripts/document_agent/architecture_validator.py` 会静态检查上述边界；Phase 6–8门禁也会
调用它。任何反向依赖、测试校验器进入生产路径或队列正文载荷都会导致门禁失败。

部署前依次运行：

```powershell
python manage.py migrate
python manage.py bootstrap_document_agent --approved-by <用户名> `
  --knowledge-index ..\docs\document_agent\private-evaluation\knowledge.json
python manage.py check_document_agent_runtime --check-providers
python manage.py run_document_generation_worker --burst
```

该命令会自动选择运行平台支持的 Worker：Windows 使用不依赖 `os.fork()` 的
`SimpleWorker`，Linux 使用标准 `Worker`；同时启用调度器以执行延迟重试任务。

前端主流程为：一次请求创建任务并绑定全部选中资料 -> 异步提取事实 -> 用户只核对关键
事实并一次确认启动生成 -> 逐章审核/批量锁定 -> 提交批准 -> 批准后导出。旧的分步 API
仍保留用于兼容，但新界面使用 `/tasks/pipeline/` 和
`/tasks/{id}/facts/confirm-and-generate/`。

任务详情每两秒增量读取 `/tasks/{id}/events/?after_sequence=N`。这种实现复用现有
Django、MySQL 和 RQ，不要求额外部署 WebSocket 服务。

章节确定性校验失败时，不会绕过规则或直接输出不合格草稿。任务会保留已通过章节，并将
失败章节及后续未完成章节写入恢复范围；队列有剩余重试次数时自动续跑，重试耗尽后前端
展示具体校验项并允许用户从失败章节继续。

执行中的会话可由有编制权限的项目成员主动停止。MySQL中的 `cancelled` 状态是最终保护，
同时向RQ发送停止或取消信号；章节和草稿持久化入口会拒绝已停止任务继续写入。非执行中
会话支持软删除并从历史列表隐藏，删除操作保留审计记录、清理私有草稿，但不删除已经
正式导出的项目文档。

生产环境只有在 `DOCUMENT_AGENT_PHASE5_APPROVED=true` 时才能启用功能；同一队列按一期
设计只运行一个 `run_document_generation_worker` 进程。

系统管理员可在 Agent 页面上传 DOCX 或文本型 PDF 作为 RAG 语料。成品四措两案可一次
选择全部适用章节，后台按标题结构拆分，只为实际识别出的章节切块并生成 Embedding；处理
记录会分别展示已索引和未识别章节。非标准单章资料或历史前置资料应只选择一个最相关章节，
此时无法识别标准标题会整篇归入该章节。RAG 语料只提供历史写法和参考知识，当前项目的
时间、地点、人员、设备等事实仍必须由该项目的入场前置资料或人工确认提供。
