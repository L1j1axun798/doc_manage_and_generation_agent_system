# 文档 Agent Phase 0：业务基线和测试样本

## 当前结论

- 当前阶段：`Phase 0`
- 当前状态：`APPROVED / 完整门禁已通过`
- 一期业务：`风电机组检测四措两案编制`
- 本目录只保存清单、字段、标签、评审和签字元数据，不保存历史文档正文。
- Phase 0 完整门禁已通过，允许继续开发 Phase 4；8份盲测正文仍不得参与 Prompt、规则、
  RAG权重或切分策略开发，只能在功能冻结后的盲测验收中使用。

## 2026-07-23 仓库基线

对当前本地开发数据库进行了只读盘点：

- `Project`：2 条；
- `Document`：176 条；
- `DocumentVersion`：176 条；
- Word 版本：16 条，其中 `.docx` 13 条、`.doc` 3 条；
- 文件名可识别为“措两案”的记录：7 条，对应 6 个唯一 SHA-256；
- 上述候选均位于公共资料目录，未关联具体项目；
- 现有 `Document` / `DocumentVersion` 没有“业务类型”和“审核通过”字段。

2026-07-23，项目方确认“技术方案”目录内的四措两案、三措两案等文档内容正确。6 个唯一
文件据此登记为已确认历史样本；另 1 条相同 SHA-256 的记录继续作为重复上传排除。

这些文件已在 Phase 0 盘点和章节结构提取中被读取，只能用于开发，不能再作为盲测样本。
2026-07-23，项目方确认将这些文件统一归类为一期业务“风电机组检测四措两案编制”。
扫塔探伤、出质保检测、塔筒焊缝、焊缝和螺栓等差异作为检测部件、检测方法和章节变化处理，
不再拆成不同的一期业务。由此，一期业务已有 6 份已确认的唯一 DOCX 开发样本。

项目方同时确认以下 3 份文档作为一期通用模板基线：

1. `风电机组质保期满检测四措两案.docx`
2. `主机设备出质保检测四措两案.docx`
3. `风机扫塔探伤项目四措两案.docx`

这里的“模板基线”表示版式、章节和内容组织方式已经选定，不表示历史成品已经改造为
带业务占位符的正式 `docxtpl` 模板。Phase 2 已于 2026-07-24 完成 3 份基线的占位符
预检和最小内存渲染验证；正式字段占位符改造仍应在接入具体业务表单时进行。

2026-07-24，按项目方“合理内容直接实现、暂缺材料保留空缺”的授权，已完成：

- 33 个一期字段及其类型、必填性、来源、示例和确认方式；
- 12 个确定性风险标签、16 条内部条款族适用映射；
- 6 份开发样本共 43 条章节边界和可复用性标注；
- 专家评分规则和空白评分卡；
- LLM 与 Embedding 技术选型及安全边界。

2026-07-24，项目方重新上传14份措两案文件。元数据和SHA-256核对结果为：5份与开发样本
重复、1份为PDF，均排除；其余8份为新增唯一DOCX，登记为B001–B008。登记过程没有读取
正文，这8份文件不得参与字段、切分、RAG权重、Prompt或规则开发。

## 文件说明

| 文件 | 用途 |
| --- | --- |
| `phase0_manifest.json` | 阶段范围、基线证据和已知缺口 |
| `business_candidates.csv` | 一期业务候选及选择证据 |
| `sample_inventory.csv` | 历史样本候选、哈希、审核状态和用途 |
| `blind_test_set.csv` | 与 Prompt、规则编写隔离的盲测集 |
| `field_dictionary.csv` | 项目字段、类型、必填性、来源和示例 |
| `risk_labels.csv` | 确定性风险标签候选 |
| `clause_applicability_matrix.csv` | 风险到审核条款的适用矩阵 |
| `template_inventory.csv` | 优先甲方模板候选 |
| `section_annotations.csv` | 历史章节定位和可复用状态 |
| `model_configuration_decision.csv` | 公司批准的 LLM 与 Embedding 决定 |
| `expert_scoring_rubric.csv` | 专家评分维度、权重和硬门槛 |
| `expert_scorecard.csv` | 后续逐项目逐章节评分记录模板 |
| `signoff_record.csv` | 技术负责人签字记录 |

字段、风险、内部条款族、章节标注、评分规则、模板基线、模型选型和盲测隔离均已按项目方
授权批准。`phase0_manifest.json`、`blind_test_set` 和 `phase0_completion` 状态均为
`approved`，允许进入 Phase 4。

内部条款族编码用于后续确定性匹配，不等同于国家或行业标准编号。正式项目仍必须根据当前
适用范围逐项确认外部标准、版本、阈值和停工条件，历史文档中的编号不能直接继承。

## 模型选型

- LLM：阿里云百炼 `qwen3.6-plus`，显式 `enable_thinking=false`，使用 JSON Mode，
  单章最多4096输出Token；
- Embedding：阿里云百炼 `text-embedding-v4`，固定 1024 维；
- 地域：华北 2（北京）`cn-beijing`；
- 接入：生产只使用业务空间专属 OpenAI 兼容域名；
- 密钥、Workspace ID 和 Endpoint 只通过环境变量提供，不写入仓库；
- 禁止敏感 Prompt/响应正文进入应用日志；生产启用前复核账号权限、费用告警和服务协议；
- 模型别名或向量维度变化必须登记版本；Embedding 变化必须重建索引。
- 两种Provider均配置超时和最多3次调用（含首次调用）；Embedding单批最多10条。

选型依据：

- https://help.aliyun.com/zh/model-studio/regions/
- https://help.aliyun.com/zh/model-studio/qwen-structured-output
- https://help.aliyun.com/zh/model-studio/embedding-rerank-model

## 一期业务选择规则

1. 只统计技术负责人确认“审核通过、内容完整、可用于 Agent”的唯一 Word 样本。
2. 同一 SHA-256 的重复上传只计 1 份。
3. 选择合格样本数量最多的业务类型。
4. 合格样本数量并列时，选择近 6 个月已完成业务项目数最多的业务类型。
5. 两项仍并列时不得由开发人员主观选择，提交技术负责人书面决定。

`business_candidates.csv` 已记录项目方确认的一期业务；具体检测对象和方法后续通过字段与
标签表达，不改变一期业务编码。

## 样本和盲测规则

- 一期业务必须有 5–20 份审核通过的唯一历史 Word。
- 至少 5 份进入盲测集。
- 盲测样本不得用于 Prompt、字段、规则、条款或切分策略编写。
- 盲测清单只向评测保管人开放；开发人员只能获得不含正文的 `blind_case_id`。
- `.doc` 文件必须先受控转换为 `.docx`，并同时保留原文件哈希和转换文件哈希。
- 原始 Word 继续通过现有文件存储和下载权限访问，不复制到 Git、Prompt 目录或测试夹具。

## 剩余人工完成顺序

1. 提供至少 5 份尚未被本次开发读取的一期 DOCX，并由独立评测保管人隔离。
2. 把这些文件登记到 `sample_inventory.csv`，用途必须为 `blind`，同时登记
   `blind_test_set.csv` 的匿名编号、保管人、隔离日期和泄漏检查结果。
3. 在进入 Phase 4 前批准 `blind_test_set`，把 Manifest 状态改为 `approved`，运行完整
   门禁。
4. 完整门禁通过后批准 `phase0_completion`；才允许实现 Phase 4 的 Prompt、规则和真实
   模型生成。

## 校验命令

在 `backend/` 目录执行：

```powershell
D:\Anaconda\envs\doc_system\python.exe scripts\document_agent\phase0_validator.py --mode structure
D:\Anaconda\envs\doc_system\python.exe scripts\document_agent\phase0_validator.py --mode development
D:\Anaconda\envs\doc_system\python.exe scripts\document_agent\phase0_validator.py --mode gate
```

- `structure`：验证文件、表头和 Manifest 结构。
- `development`：验证允许 Phase 1–3 的业务基线；当前必须通过。
- `gate`：验证进入 Phase 4 前的完整基线，包括盲测隔离和最终签字；当前只应因新增盲测
  材料及其派生的最终签字未完成而失败。

## 数据和安全边界

- 不向代码库写入 Word 正文、客户名称、电话、身份证号、人员名单或生产绝对路径。
- 不在 CSV 中写 API Key、模型密钥、访问令牌或真实服务 URL。
- 不把“上传时间”当作“业务发生时间”，不把“位于技术方案目录”当作“审核通过”。
- 历史内容只能作为候选参考，不能覆盖当前项目确认事实和已批准条款。
- Phase 0 不新增 Django 模型、API、前端页面、RQ/Redis、Prompt 或生成代码。
