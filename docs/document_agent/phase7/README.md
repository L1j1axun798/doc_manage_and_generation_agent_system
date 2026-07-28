# Document Agent Phase 7

Phase 7 已接入单一 `document-generation` RQ 队列。Web 请求只落库并在事务提交后入队，
事实提取和四措两案生成均由 Worker 执行。

固定约束：

- Job 参数只包含 `GenerationTask` UUID，Job ID 也使用该 UUID；
- 超时 30 分钟，失败重试 2 次，间隔 60 秒和 300 秒；
- Redis 只保存任务调度信息，正文、Prompt、合同和生成文件不进入 Redis；
- MySQL 是任务、章节、状态和审核记录的唯一权威来源；
- 每章生成后立即写入 MySQL，锁定章节不会被重复生成；
- 重复 Job 会安全跳过，正式文档版本只在批准后的导出动作创建一次；
- Redis 不可用时只把当前生成任务标记为失败，原资料管理系统继续工作；
- Worker 启动命令先恢复遗留的 `extracting`、`queued` 和超时 `generating` 任务。
- `run_document_generation_worker --burst` 可在部署前验证真实Redis连接和Worker启动，
  该命令在 Windows 自动使用 `SimpleWorker`，并启用调度器处理延迟重试；
  处理完当前队列后正常退出。

LLM和Embedding适配器也有独立的限时与有上限瞬时故障重试；Embedding按服务限制每批
最多10条。章节第一次确定性校验失败时，只允许模型按明确错误修订一次，之后必须重新通过
同一套严格校验，不会以降低安全或来源门禁换取成功。

开发/测试可显式使用 Fake Provider；生产配置检测到 Fake Provider 会拒绝启动。
