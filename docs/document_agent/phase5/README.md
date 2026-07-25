# Document Agent Phase 5

离线CLI、盲测案例登记表、逐章评分表和自动门禁汇总器已经实现。B001、B005、B008
已由项目方提供的独立来源资料形成私有输入包，并分别完成8章节Fake Provider冒烟测试和
真实Provider生成；每个案例的确定性校验均为 `valid=true`、事实引用覆盖率为 `1.0`，
真实模型用量存在且无Fake调用。技术负责人评分和人工耗时仍未完成。

扫描版合同和委托单仍由人工逐页核对后转录为带来源页码的私有事实底稿，生产解析器没有
为了本次测试放宽“扫描PDF不可直接解析”的规则。事实底稿、原件、输入JSON和输出均位于
Git已忽略的 `docs/document_agent/phase5/private/`。

```powershell
D:\Anaconda\envs\doc_system\python.exe backend\scripts\document_agent\phase5_cli.py `
  --input .\docs\document_agent\phase5\offline_input.example.json `
  --output-dir .\offline-output `
  --provider real `
  --env-file .\backend\.env
```

输出固定为：

- `entry_plan.docx`
- `trace.json`
- `validation.json`
- `review_bundle.json`（逐章正文、引用候选、检索轨迹、校验问题和真实模型用量）

`review_bundle.json` 还包含当前生成实现指纹；评测时若代码、Provider、Prompt或校验规则
已经变化，旧输出会以 `IMPLEMENTATION_FINGERPRINT_MISMATCH` 被拒绝。

失败时额外写入 `failure.json`，保留错误码、确定性校验问题和失败轨迹，便于修复；成功重跑
会自动移除旧的失败文件。密钥、Endpoint和完整Prompt不会写入这些产物。

## 私有输入准备

开发人员先把逐页核对后的事实写入私有 `facts.json`，再运行两个可复用工具。第一个工具
生成可视核对的DOCX事实底稿和精确段落定位；第二个工具校验事实底稿哈希及批准模板哈希，
生成CLI输入JSON：

```powershell
python backend\scripts\document_agent\phase5_fact_sheet.py `
  --input .\docs\document_agent\phase5\private\B005\facts.json `
  --output .\docs\document_agent\phase5\private\B005\fact_sheet.docx

python backend\scripts\document_agent\phase5_input_builder.py `
  --locators .\docs\document_agent\phase5\private\B005\fact_sheet.locators.json `
  --template-id T001 `
  --template-path .\docs\document_agent\phase5\private\shared\approved_template_T001.docx `
  --output .\docs\document_agent\phase5\private\B005\input.json
```

事实底稿中的 `confirmed_by=1` 只是离线准备人占位，不映射生产用户，也不代表技术负责人
已经审核。金额、付款、银行账户、电话和身份证号不得转录到事实底稿。

离线CLI会在模型生成前解析事实底稿，并逐项确认 `source_document_version_id` 属于本次
输入、`paragraph_index/page/table_index/text_quote` 能命中真实解析块。仅在JSON里填写
一个看似合法但不存在的定位会以 `FACT_EVIDENCE_INVALID` 失败。

T001–T003当前是含历史正文的无占位符版式基线。渲染器已增加样式基线安全模式：从全新
DOCX包开始，仅复制样式、编号和页面参数，不复制旧正文、页眉页脚、图片或附件。Phase 5
私有输出已检查，不含基线中的历史项目实体，DOCX包内也没有遗留 `word/media/` 资源。

真实评测前，先用已批准的Embedding服务从6份开发样本构建本地JSON索引，再把路径填写到
各案例输入JSON的 `knowledge_json_path`。该索引包含历史章节正文，只能保存在受控本地
目录，不得提交Git：

```powershell
D:\Anaconda\envs\doc_system\python.exe backend\scripts\document_agent\phase3_evaluator.py `
  --embedding-provider real `
  --env-file .\backend\.env `
  --output-index .\docs\document_agent\private-evaluation\knowledge.json `
  --overwrite
```

## 评测操作

1. 在 `evaluation_cases.csv` 中为至少3个案例填写当前项目 `input_json_path` 和
   `output_directory`，并把 `input_bundle_status` 改为 `ready`。
2. 使用真实Provider逐案例运行CLI；成功后填写 `generation_provider=real` 和
   `generation_status=completed`。
3. 运行 `phase5_scorecard_builder.py` 生成24行私有评审表；技术负责人按章节填写评分、
   硬门禁判断和两类耗时，完成后把案例的
   `review_status` 改为 `completed`。
4. 运行门禁：

```powershell
D:\Anaconda\envs\doc_system\python.exe `
  backend\scripts\document_agent\phase5_preparation_validator.py

D:\Anaconda\envs\doc_system\python.exe `
  backend\scripts\document_agent\phase5_scorecard_builder.py

D:\Anaconda\envs\doc_system\python.exe backend\scripts\document_agent\phase5_evaluator.py `
  --scorecard .\docs\document_agent\phase5\private\evaluation_scorecard.review.csv `
  --output .\docs\document_agent\private-evaluation\phase5-v1-summary.json
```

第一条命令检查盲测案例映射和预评测冻结哈希；最后一条命令检查真实模型用量记录、四个输出
文件、事实引用覆盖率，并根据Phase 0已批准
规则计算：重大虚构=0、重大安全技术遗漏=0、数字来源完整、历史项目污染=0、RAG Hit@3
不少于80%、`manual_editing_effort >= 4` 的章节不少于70%、专业可用性平均分不少于4、
总人工时间降低不少于50%。`changed_character_ratio`保留为评测指标，不单独设置未经批准
的硬阈值。

当前3个独立输入案例B001、B005、B008已经完成真实Provider生成并满足加急评测数量要求，
不再要求项目方继续补充案例。Phase 6–8可以在功能默认关闭的条件下继续开发；但技术负责
人逐章评分和人工耗时记录尚未完成，因此仍不得生产启用。B001–B008对应的四措两案答案
文档只供后续独立评审，不是生成输入。门禁会读取输入JSON中的
`document_version_id`，如果引用了任一盲测答案版本，将以
`BLIND_ANSWER_USED_AS_INPUT` 直接失败；离线CLI也会在读取来源文件正文前执行同一黑名单
检查并拒绝运行。

本次补充目录中另有4份四措两案文件。它们被隔离为答案候选，未打开正文、未进入事实底稿、
未进入RAG，也不计作当前项目输入。含身份证号的登记表副本和检测范围不一致的材料副本已
移入私有 `quarantine/`，不会被评测读取，外部原文件未改动。

这些配对输入资料由项目方直接提供给开发人员后，放入Git已忽略的
`docs/document_agent/phase5/private/`或其他受控本地目录；不上传现有文档管理系统、不进入
RAG，也不随生产部署迁移。完整合同不是必需输入，优先使用删除金额、付款和账户信息后的
脱敏资料。

本地受控 `.env` 已配置并通过 `qwen3.7-plus` 与 `text-embedding-v4/1024` 的真实连通
检查；根路径必须使用阿里云OpenAI兼容的 `/compatible-mode/v1`。LLM显式关闭思考模式、
限制单章输出Token并记录用量；LLM和Embedding均对限流、超时及服务端瞬时错误执行有上限
重试。任何密钥和真实Endpoint都不得写入Git。

评测器只选择 `input_bundle_status=ready` 的案例；其余已登记但尚无配对输入的盲测案例不会
误报为输入缺失。每个入选案例必须严格具有8个唯一章节评分、真实模型用量和完整
`review_bundle.json`。技术负责人评分与真实人工耗时不能由开发人员或模型代填。
