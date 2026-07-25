

## Summary

仓库根目录：

```
D:\vscode程序夹\wind-doc-system\CODEX_DOCUMENT_AGENT_GUIDE.md
```

该文档是“入场四措两案编制”Agent开发期间的技术参考，搭配
`分阶段开发任务.md` 使用。

Codex每次开始相关任务前必须完整阅读。Phase 1–9 仍按顺序实施；Phase 0 采用下述两级门禁，
达到开发门禁后可依次实施 Phase 1–3，达到完整门禁后才可进入 Phase 4。

### 业务目标和时间边界

Agent 的唯一核心目标，是在人员、设备或检测作业入场/开工前，根据当前项目资料，自动生成或
辅助完成《四措两案》的撰写，供内部审核、入场报审和现场作业准备使用。

本功能的输入是编制入场方案所需的当前项目资料，例如：

- 项目、甲方、场站和工作范围；
- 计划检测对象、计划数量、检测方法和计划工期；
- 拟入场人员、职责、资质、工器具、仪器设备和个人防护用品；
- 甲方模板、技术协议、任务通知、安全要求、环保要求和现场约束。

本功能的输出是“入场前四措两案 DOCX 初稿/审核稿/批准稿”，不是作业完成后的成果报告。

以下内容明确不属于本 Agent：

- 检测报告、试验报告、验收报告、完工报告和竣工资料；
- 实测数据、检测结果、缺陷清单、处理结果和检测结论；
- 向甲方提交的完工成果报告及其报告模板；
- 根据完工数据反向生成或补写四措两案。

后文出现的“项目资料”“来源资料”“生成文档”和“导出”，除非明确说明，均分别指
“入场方案编制资料”“四措两案”和“四措两案 DOCX 导出”。任何后续实现不得把本功能扩展
为检测报告生成器。

Phase 5盲测所需的配对输入资料由项目方直接提供到受控本地评测目录，不上传现有文档管理
系统、不提交Git、不进入RAG，也不随生产部署迁移。生产接入不得为合同等敏感资料新增根
分类或专用上传功能；正式功能使用结构化表单，并仅允许选择系统中原本已经存在且当前用户
有权读取的文档。Agent不要求上传包含金额、付款、账户等商业信息的完整合同。

截至2026-07-25，B001、B005、B008已有独立来源输入包，均已完成真实Provider八章节
生成；确定性校验、事实引用覆盖率、实现指纹和逐页排版自检通过。这3个案例已满足加急评测
数量要求。另有4份四措两案仅隔离为答案候选，正文不得用于事实底稿、Prompt、RAG或规则。
Phase 5现在只剩技术负责人逐章评分和人工耗时记录，不得由开发人员或模型代填。

项目方已批准加急门禁：3个独立案例允许Phase 6–8在功能默认关闭的条件下继续开发；在
Phase 5真实评测门禁通过前，禁止打开生产功能开关、导入生产数据或用于实际四措两案编制。

### 两级阶段门禁

Phase 0 不再用盲测材料阻塞核心基础开发：

1. `Phase 1–3 开发门禁`
   - 一期业务、5–20份开发样本、模板基线、字段、风险与条款、章节标注、模型配置和评分规则
     已批准；
   - 通过该门禁后，允许依次开发 Phase 1、Phase 2 和 Phase 3；
   - 此时 Phase 0 状态记为 `baseline_ready`，不代表完整验收完成。
2. `Phase 4 前完整门禁`
   - 在开发人员接触盲测正文前，由独立保管人隔离至少5份新增盲测样本；
   - 盲测样本不得参与字段、切分、RAG权重、Prompt、风险规则或条款规则编写；
   - 盲测清单和 Phase 0 最终完成记录签字后，状态才改为 `approved`；
   - 未通过该门禁不得进入 Phase 4，不得编写或调优真实生成Prompt和规则，也不得进行
     Phase 5效果验收。

固定技术栈：

```
后端：Django 5.2 + DRF
前端：Vue 3 + TypeScript + Element Plus
数据库：现有MySQL 8
任务队列：RQ + Redis
数据校验：Pydantic 2
Word：docxtpl + python-docx
PDF：pypdf，仅支持文本型PDF
RAG：元数据过滤 + Embedding + 应用内相似度计算
模型：云端模型Provider适配层
部署：原生Linux服务 + systemd
存储：现有文件存储
```

明确不使用Docker、Celery、自研MySQL队列、微服务、LangChain/LangGraph、独立向量数据库、在线Word编辑器、本地大模型和扫描件OCR。

## 一、架构和目录约束

新增三个边界清晰的模块：

```
backend/apps/document_generation/engine/
    纯Python核心，不依赖Django ORM、Request和用户会话

backend/apps/document_generation/
    Django模型、API、权限、RQ任务和现有平台适配

fronted/src/modules/document-generation/
    项目输入、确认、进度、审核和导出界面
```

核心依赖方向固定为：

```
Django适配层 → Agent核心
RQ Worker    → Agent核心
离线评测CLI  → Agent核心

Agent核心不得反向依赖Django、RQ或前端
```

Agent不是开放式自主Agent，而是入场方案编制的确定性工作流：

```
入场编制资料解析
→ 事实抽取
→ 人工确认
→ 风险识别
→ 条款选择
→ RAG检索
→ 分章生成
→ 规则校验
→ 人工审核
→ Word渲染
→ 四措两案归档
```

不用ReAct循环，不允许模型自由决定下一步，不允许模型直接执行写数据库、批准、导出或归档操作。

## 二、核心接口和Tools

### 1. 核心Ports

在 `engine` 内定义以下抽象接口：

- `SourceParser`
  - 输入：文件流、文件名、MIME类型
  - 输出：标题树、段落、表格、来源定位和文本哈希
- `LLMProvider`
  - `extract_facts()`
  - `draft_section()`
  - `repair_structured_output()`
  - 不包含数据库和文件操作
- `EmbeddingProvider`
  - 输入：文本列表
  - 输出：等维向量列表
  - 记录模型别名和向量维度
- `KnowledgeRepository`
  - 保存和查询历史章节
  - 离线阶段使用内存或JSON实现
  - 平台阶段使用Django ORM实现
- `ClauseRepository`
  - 按章节和风险标签返回审核条款
- `TemplateRenderer`
  - 输入：模板、确认事实和章节
  - 输出：DOCX文件和渲染校验结果
- `ArtifactStorage`
  - 保存离线评测产物或调用现有文件存储
  - 正式产物归入当前项目的技术方案/入场资料，不得归入检测报告或竣工资料
  - 核心代码不接触绝对生产路径

### 2. 内部Tools

Tools是有类型的Python服务，不是任意模型工具调用。

固定Tools：

- `parse_source_document`
- `extract_fact_candidates`
- `validate_fact_set`
- `build_risk_profile`
- `select_clause_blocks`
- `retrieve_reference_sections`
- `build_section_context`
- `draft_document_section`
- `validate_document_section`
- `render_word_document`
- `publish_document_version`

调用权限：

| Tool             | 工作流调用 | 模型可直接调用             |
| ---------------- | ---------- | -------------------------- |
| 入场编制资料解析 | 是         | 否                         |
| 事实抽取         | 是         | 仅返回候选值               |
| 风险识别         | 是         | 仅提供建议，规则最终决定   |
| 条款选择         | 是         | 否                         |
| RAG检索          | 是         | 否                         |
| 章节生成         | 是         | 是，通过固定Prompt和Schema |
| 章节校验         | 是         | 否                         |
| Word渲染         | 是         | 否                         |
| 审核、批准、归档 | 是         | 否                         |

模型只负责候选事实抽取和章节草稿，不掌握审批与写操作权限。

### 3. Pydantic契约

至少定义：

- `ParsedDocument`
- `ParsedBlock`
- `SourceLocator`
- `FactCandidate`
- `ConfirmedFact`
- `RiskProfile`
- `ClauseSelection`
- `RetrievalQuery`
- `RetrievedSection`
- `SectionContext`
- `GeneratedSection`
- `ValidationIssue`
- `GenerationTrace`

事实结构固定包含：

```
{
  "field": "planned_inspection_quantity",
  "value": 24,
  "value_type": "integer",
  "source_document_version_id": 123,
  "locator": {
    "heading_path": ["一、概况", "1.2 工作范围"],
    "paragraph_index": 8,
    "page": null
  },
  "confidence": 0.96,
  "confirmed_by": 18
}
```

DOCX没有稳定页码，使用标题路径和段落序号定位；PDF使用页码和文本片段定位。

章节输出固定包含：

```
{
  "section_code": "technical_measures",
  "title": "技术措施",
  "paragraphs": [],
  "citations": [],
  "used_clause_ids": [],
  "missing_items": [],
  "warnings": []
}
```

## 三、RAG实现方式

### 1. RAG用途

RAG只用于检索审核通过的历史章节，为变化章节提供专业表达和类似做法。

RAG不负责：

- 提供当前项目事实
- 决定安全条款
- 替代技术标准库
- 直接复制整篇历史文档
- 提供实测数据、缺陷或完工事实
- 自动生成检测结论或任何完工成果报告

生成上下文的优先级固定为：

```
确认后的项目事实
> 审核通过的标准和条件条款
> 审核通过的历史参考章节
```

出现冲突时，历史案例不得覆盖当前项目事实和条款。

### 2. 文档切分

禁止按固定字符数直接切完整文档。

按以下顺序切分：

1. 识别Word标题样式和编号。
2. 建立章节树和标题路径。
3. 删除目录、重复页眉页脚、纯页码。
4. 保留有意义的列表、表格标题、单位和标准编号。
5. 一个小节优先作为一个Chunk。
6. 小节超过1,000个中文字符时，按段落切成400–1,000字符的Chunk。
7. 长章节切分时保留约100字符上下文重叠。
8. 表格Chunk必须同时包含表头和对应行。
9. 每个Chunk保存来源文档版本、标题路径和段落范围。

Chunk元数据：

```
{
  "source_document_version_id": 123,
  "business_type": "一期检测业务编码",
  "client_code": "甲方编码",
  "section_code": "construction_plan",
  "heading_path": ["六、施工方案", "6.2 检测流程"],
  "component_tags": [],
  "method_tags": [],
  "risk_tags": [],
  "approval_status": "approved",
  "content_sha256": "..."
}
```

### 3. Embedding和存储

- Embedding通过 `EmbeddingProvider` 调用公司批准的云端服务。
- Embedding只针对审核通过的历史章节生成。
- 文本哈希、模型别名和维度相同则复用已有向量。
- 文本、模型或切分规则变化时重新生成。
- 一期向量保存在 `KnowledgeSection.embedding` JSON字段。
- 使用NumPy在应用内计算余弦相似度。
- 当前数据超过5,000个有效Chunk后，才重新评估独立向量数据库。

### 4. 检索流程

每个变化章节单独检索：

1. 使用 `business_type` 和 `section_code` 硬过滤。
2. 根据检测部件、方法和风险标签过滤或加权。
3. 生成检索查询，内容只来自确认事实和当前章节目标。
4. 计算Embedding余弦相似度。
5. 最终评分：

```
0.60 × 向量相似度
+ 0.25 × 标签匹配度
+ 0.10 × 检测方法匹配度
+ 0.05 × 甲方匹配度
```

1. 取前8个候选。
2. 去除同一来源中高度重复的Chunk。
3. 最多向模型提供3个参考Chunk。
4. 没有达到最低相似度的案例时，不提供历史案例，不强行凑数。

每个引用保存：

- 来源文档版本
- Chunk ID
- 标题路径
- 相似度
- 使用位置

引用只在审核界面和生成追踪中显示，默认不写入正式Word正文。

### 5. 防止历史内容污染

生成后必须检查：

- 历史甲方名称
- 历史项目名称
- 历史场站名称
- 不属于当前项目的人员和设备
- 历史日期和数量
- 未经当前资料确认的标准编号
- 历史实测数据、缺陷、处理结果和检测结论

发现污染时将章节标记为 `VALIDATION_FAILED`，不得进入审核通过状态。

## 四、模型调用和Prompt

### 1. Provider适配

具体供应商和模型通过环境变量配置：

```
LLM_PROVIDER
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
LLM_ENABLE_THINKING
LLM_MAX_TOKENS
LLM_TIMEOUT_SECONDS
LLM_MAX_ATTEMPTS
EMBEDDING_BASE_URL
EMBEDDING_API_KEY
EMBEDDING_MODEL
EMBEDDING_DIMENSION
EMBEDDING_BATCH_SIZE
EMBEDDING_MAX_ATTEMPTS
```

Codex不得自行在业务代码中硬编码模型名称。

每个Provider必须实现：

- 结构化JSON输出
- 超时
- 限流错误识别
- 可重试错误分类
- Token和费用统计
- 请求ID记录
- 不记录完整敏感Prompt

### 2. Prompt文件

Prompt独立版本化，不散落在services和views中：

```
prompts/fact_extraction/v1.md
prompts/section_generation/v1.md
prompts/section_revision/v1.md
prompts/schema_repair/v1.md
```

Prompt必须明确：

- 只能使用提供的事实、条款和参考章节。
- 只编写入场前的计划、组织、技术、安全、环保、施工和应急内容。
- 不得输出实测数据、检测结果、缺陷、处理结果或检测结论。
- 不得生成检测报告、完工报告、验收报告或竣工资料内容。
- 不得补造缺失信息。
- 缺失信息写入 `missing_items`。
- 不确定内容写入 `warnings`。
- 不得输出Schema之外的字段。
- 不得把历史案例中的专有信息带入新项目。

### 3. 调用方式

- 事实抽取：按来源文档执行，返回候选事实。
- 章节生成：每章单独调用。
- 安全、环保、应急章节：先装配确定性条款，再让模型完成项目化连接和表述。
- Schema解析失败：最多执行一次结构修复调用。
- 章节确定性校验失败：携带明确错误最多修订一次，再用同一门禁复检；禁止放宽规则。
- API瞬时错误：使用Tenacity执行最多3次调用（含首次调用）。
- Embedding按服务限制每批最多10条。
- 整体Job失败：由RQ再重试2次。
- 已成功保存的章节不得在Job重试时重复生成。

## 五、Word模板和渲染

### 1. 模板规范

每套甲方模板必须包含：

- 模板编码和版本
- 适用甲方
- 适用业务类型
- 封面字段
- 标题样式映射
- 页眉页脚
- 表格样式
- 章节顺序
- 必需占位符
- 是否启用

`docxtpl`负责：

- 封面字段
- 项目基础字段
- 固定表格变量
- 简单条件块

`python-docx`负责：

- 动态章节
- 多级标题
- 段落和列表
- 动态表格
- 分页符
- 目录字段
- `w:updateFields`设置

当前T001–T003是项目方批准的“版式/章节样式基线”，不是已经参数化的空白模板：文件仍含
历史项目正文且没有Jinja占位符。对这类无占位符基线，渲染器必须创建全新DOCX包，只复制
样式、编号和页面参数，再写入当前项目封面与生成章节；不得复制历史正文、页眉页脚、图片、
附件或其他包内资源。只有经过专项清理并配置占位符的模板，才允许保留模板正文渲染。

一期不通过LibreOffice生成PDF预览；前端直接显示入场四措两案章节文本，最终导出DOCX。

### 2. 模板校验

模板进入启用状态前检查：

- 必需占位符是否存在
- 占位符是否重复或拼写错误
- 必需标题样式是否存在
- 章节映射是否完整
- 是否残留测试文本
- 是否能使用最小测试数据成功生成DOCX

模板文件继续作为现有 `DocumentVersion` 保存，不在数据库保存二进制内容。

## 六、数据库、状态机和API

### 1. 新增模型

- `DocumentTemplate`
  - 模板编码、甲方、业务类型、版本
  - 模板 `DocumentVersion`
  - 字段映射、章节顺序、启停和审核信息
- `ClauseBlock`
  - 条款编码、章节、正文
  - 风险条件、版本、启停和审核信息
- `KnowledgeSection`
  - 来源文档版本、章节、正文、定位
  - 业务标签、风险标签、向量和审核状态
- `GenerationTask`
  - UUID、项目、模板、业务类型
  - 文档用途固定为入场四措两案，不接受检测报告或完工资料用途
  - 状态、进度、事实快照、风险画像
  - Provider、模型、Prompt和切分规则版本
  - 创建人、审核人、错误码和导出结果
- `GenerationSource`
  - 任务、来源文档版本
  - 文件哈希、解析状态和解析错误
- `GeneratedSection`
  - 任务、章节编码、正文、引用
  - 修订号、锁定状态和校验结果
- `GenerationReview`
  - 任务或章节、动作、意见、操作人和时间

所有迁移只新增表、索引和外键，不修改现有文档表核心结构。

### 2. 状态机

```
DRAFT
→ EXTRACTING
→ NEEDS_CONFIRMATION
→ READY
→ QUEUED
→ GENERATING
→ REVIEW_REQUIRED
→ APPROVED
→ EXPORTED
```

失败进入：

```
FAILED
```

错误码至少包括：

- `DOCUMENT_PURPOSE_INVALID`
- `SOURCE_PURPOSE_MISMATCH`
- `RESULT_CONTENT_FORBIDDEN`
- `SOURCE_UNSUPPORTED`
- `SOURCE_PARSE_FAILED`
- `FACTS_INCOMPLETE`
- `FACTS_CONFLICT`
- `QUEUE_UNAVAILABLE`
- `MODEL_TIMEOUT`
- `MODEL_RATE_LIMITED`
- `MODEL_SCHEMA_INVALID`
- `RETRIEVAL_EMPTY`
- `TEMPLATE_INVALID`
- `VALIDATION_FAILED`
- `EXPORT_FAILED`

### 3. RQ和Redis

固定配置：

```
Queue：document-generation
Worker：1个
Job参数：仅GenerationTask UUID
Job ID：GenerationTask UUID
Job超时：30分钟
Job重试：2次
重试间隔：60秒、300秒
```

实现要求：

- 使用 `transaction.on_commit()` 入队。
- Worker领取任务后重新检查数据库状态。
- 状态不是 `QUEUED` 时Job直接安全退出。
- 每完成一个章节立即保存，Job重试时跳过已完成章节。
- Redis不可用时API返回明确错误，原资料系统继续工作。
- Worker启动时检查遗留的 `QUEUED` 和超时 `GENERATING` 任务。
- Redis只监听本机，使用AOF、`noeviction`和内存上限。
- 不在Redis中存储合同、Prompt正文、章节正文和生成文件。

### 4. API

统一前缀：

```
/api/v1/document-generation/
```

接口：

```
GET   /templates/
POST  /tasks/
GET   /tasks/{id}/
POST  /tasks/{id}/sources/
POST  /tasks/{id}/extract/
PUT   /tasks/{id}/facts/confirm/
POST  /tasks/{id}/generate/
PATCH /tasks/{id}/sections/{code}/
POST  /tasks/{id}/sections/{code}/lock/
POST  /tasks/{id}/sections/{code}/regenerate/
POST  /tasks/{id}/submit-review/
POST  /tasks/{id}/approve/
POST  /tasks/{id}/export/
```

规则：

- 创建、生成和导出支持幂等键。
- 创建任务时文档用途必须为 `entry_four_measures_two_plans`；其他用途返回
  `DOCUMENT_PURPOSE_INVALID`。
- 报告模板或明显属于完工成果的来源不得进入事实抽取和RAG，返回
  `SOURCE_PURPOSE_MISMATCH`。
- 导出成功后只创建一个正式的入场四措两案 `DocumentVersion`。
- 导出文件必须关联当前项目并归入技术方案/入场资料语义，不得进入“报告模板”、
  “检测报告”或“竣工资料档案”。
- 前端每2秒轮询生成状态；任务结束或页面离开时停止轮询。
- 归档项目禁止创建、生成和导出。
- 临时用户禁止访问全部生成接口。

### 5. Phase 6–8加急开发状态（2026-07-25）

项目方批准以3个独立案例继续开发后，Phase 6–8已经完成代码实现和开发门禁自检，但功能
仍保持关闭：

- Phase 6：新增模型和迁移、ORM仓储、项目权限、状态机、幂等、审计及导出API；
- Phase 7：单一RQ队列、UUID唯一载荷、事务提交后入队、超时重试、逐章持久化和遗留任务
  恢复；
- Phase 8：项目页签、已有资料选择、事实确认、进度轮询、逐章编辑/锁定/重生、批准和导出；
- 后端必须同时打开 `DOCUMENT_AGENT_ENABLED` 与 `DOCUMENT_AGENT_PHASE5_APPROVED`；
- 前端还必须打开 `VITE_DOCUMENT_AGENT_ENABLED`；
- 生产环境禁止Fake Provider，启用时强制检查真实模型/Embedding配置和本机Redis；
- 批准模板、条款和RAG索引通过幂等初始化命令导入；运行时检查命令验证数据库、Redis和
  可选真实Provider；纯引擎和平台适配层由架构门禁隔离；
- 当前 `DOCUMENT_AGENT_PHASE5_APPROVED=false`；3个案例已完成真实模型运行，但在技术
  负责人评分和人工耗时验收前仍不得改为true。



## 七、Codex工作纪律

每次任务开始：

1. 阅读本文件和适用仓库指令。
2. 确认当前Phase。
3. 若当前工作处于 Phase 1–3，确认 Phase 0 开发门禁已通过；若准备进入 Phase 4 或更高
   阶段，确认 Phase 0 完整门禁已通过。
4. 检查工作树和现有未提交修改。
5. 阅读相关代码和测试。
6. 只实施本Phase明确列出的工作。
7. 不提前添加未来基础设施。

每次任务结束必须报告：

- 当前Phase。
- 修改文件。
- 实现的Tools和接口。
- 数据库或API变化。
- 实际执行的命令。
- 测试结果。
- 人工验证步骤。
- 未验证范围。
- 是否达到Phase完成门槛。
- 下一步允许进行的工作。

测试命令按变更范围执行：

```
后端：
python -m pytest <相关测试>
python -m ruff check apps common
python manage.py check
python manage.py makemigrations --check --dry-run

前端：
npm run type-check
npm run lint
npm run test:unit
npm run build
```

只有在实际执行成功后，才能标记阶段完成。
