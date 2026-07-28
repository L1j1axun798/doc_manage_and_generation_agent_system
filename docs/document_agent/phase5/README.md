# Document Agent Phase 5

离线CLI、盲测案例登记表、逐章评分表和自动门禁汇总器已经实现。第一次专家反馈确认旧稿
存在横向纸张、样式失真、内容偏短和专业完整度不足，旧评分保留为失败反馈，不作为通过
依据。质量修复后的 `phase5-v2` 中，B001、B005、B008均已使用 `qwen3.6-plus` 完成
8章真实Provider生成，有效字符分别为18021、21608、21262；三份均为A4纵向，确定性校验
`valid=true`、事实引用覆盖率为 `1.0`，实现指纹一致。
技术负责人已完成24章评分，最终门禁 `status=passed`：RAG Hit@3为87.5%，小改章节比例
为75%，专业可用性平均4.0，重大虚构、重大安全技术遗漏、无来源数字和历史项目污染均为0。
项目方明确确认本轮无法可靠估算两类人工耗时，因此使用可审计的
`time_gate_status=waived_by_project_owner`，没有伪造分钟数。完成表保存在
`docs/document_agent/phase5/private/evaluation_scorecard.phase5-v2.completed.csv`。

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
3. 运行 `phase5_scorecard_builder.py` 生成24行私有评审表；生成器只预填章节和客观上下文，
   所有人工判断列保持空白；技术负责人按章节填写评分、
   硬门禁判断和两类耗时，完成后把案例的
   `review_status` 改为 `completed`。
4. 运行门禁：

评分表按以下中文含义填写；同一项目的 `baseline_minutes` 和
`agent_assisted_minutes` 在8章中重复填写同一组总耗时：

| 列名 | 直白含义 | 填法 |
| --- | --- | --- |
| `reviewer` | 评审人 | 姓名或工号，不能为空 |
| `reviewed_at` | 评审时间 | 例如 `2026-07-26 14:30` |
| `factual_accuracy` | 事实是否准确 | 1很差，5完全准确 |
| `source_traceability` | 事实能否查回原资料 | 1不可追溯，5全部清楚 |
| `clause_correctness` | 条款是否用对 | 1严重错误，5正确完整 |
| `safety_technical_completeness` | 安全技术内容是否完整 | 1严重缺漏，5完整 |
| `current_project_consistency` | 是否混入别的项目 | 1污染严重，5完全一致 |
| `professional_usability` | 专业人员能否直接使用 | 1不可用，5可直接使用 |
| `manual_editing_effort` | 修改工作量，分越高改得越少 | 1基本重写；2大改；3中等修改；4小改；5几乎不用改 |
| `major_fabricated_fact` | 有无重大编造 | 有填 `TRUE`，没有填 `FALSE` |
| `major_safety_or_technical_omission` | 有无重大安全技术遗漏 | 有填 `TRUE`，没有填 `FALSE` |
| `all_numbers_have_sources` | 所有数字是否有来源 | 都有填 `TRUE`，否则 `FALSE` |
| `historical_entity_contamination` | 是否混入历史项目专有信息 | 有填 `TRUE`，没有填 `FALSE` |
| `rag_hit_at_3` | 前3条参考是否至少一条有用 | 有填 `TRUE`，没有填 `FALSE` |
| `changed_character_ratio` | 实际修改文字比例 | 0到1；如改了约20%填 `0.2` |
| `baseline_minutes` | 不用Agent时该项目总编制分钟数 | 正数；每章重复同一值 |
| `agent_assisted_minutes` | 使用Agent后该项目总用时 | 正数；每章重复同一值 |
| `review_comments` | 问题说明 | 用中文写具体问题，可留空 |

`manual_editing_effort=5` 表示“几乎不用改”，不能把“修改很多”填成5分。例如实际修改
约70%时，`changed_character_ratio=0.7`，人工修改工作量通常不应再评为4或5分。

```powershell
D:\Anaconda\envs\doc_system\python.exe `
  backend\scripts\document_agent\phase5_preparation_validator.py

D:\Anaconda\envs\doc_system\python.exe `
  backend\scripts\document_agent\phase5_scorecard_builder.py `
  --output .\docs\document_agent\phase5\private\evaluation_scorecard.phase5-v2.review.csv

D:\Anaconda\envs\doc_system\python.exe backend\scripts\document_agent\phase5_evaluator.py `
  --scorecard .\docs\document_agent\phase5\private\evaluation_scorecard.phase5-v2.completed.csv `
  --output .\docs\document_agent\private-evaluation\phase5-v2-final-summary.json `
  --waive-time-gate
```

第一条命令检查盲测案例映射和预评测冻结哈希；最后一条命令检查真实模型用量记录、四个输出
文件、事实引用覆盖率，并根据Phase 0已批准
规则计算：重大虚构=0、重大安全技术遗漏=0、数字来源完整、历史项目污染=0、RAG Hit@3
不少于80%、`manual_editing_effort >= 4` 的章节不少于70%、专业可用性平均分不少于4、
总人工时间降低不少于50%。`changed_character_ratio`保留为评测指标，不单独设置未经批准
的硬阈值。默认仍强制要求两类耗时；只有项目方作出显式、留痕的豁免决定时，才允许使用
`--waive-time-gate`，此时汇总结果必须显示 `time_gate_status=waived_by_project_owner`。

当前3个独立输入案例B001、B005、B008已满足加急开发的输入数量要求，不再要求项目方继续
补充案例；三个 `phase5-v2` 案例已全部完成真实模型生成和技术负责人逐章评分，Phase 5
真实评测门禁已通过。生产启用条件已具备，但本次评测不会自动修改任何环境功能开关。
B001–B008对应的四措两案答案文档只供后续独立
评审，不是生成输入。门禁会读取输入JSON中的
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

本地受控 `.env` 已配置，并通过 `qwen3.6-plus` 与 `text-embedding-v4/1024` 的真实
连通检查；三个新版案例均已由该LLM完成生成。根路径必须使用阿里云OpenAI兼容的
`/compatible-mode/v1`。LLM显式关闭思考模式、限制单章输出Token并记录用量；LLM和
Embedding均对限流、超时及服务端瞬时错误执行有上限重试。任何密钥和真实Endpoint都不得
写入Git。

评测器只选择 `input_bundle_status=ready` 的案例；其余已登记但尚无配对输入的盲测案例不会
误报为输入缺失。每个入选案例必须严格具有8个唯一章节评分、真实模型用量和完整
`review_bundle.json`。技术负责人评分不能由开发人员或模型代填；未被项目方显式豁免时，
真实人工耗时也不能由开发人员或模型代填。
