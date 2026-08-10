from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

BUSINESS_TYPE = "wind_turbine_inspection_four_measures_two_plans"
DOCUMENT_PURPOSE = "entry_four_measures_two_plans"


class ApprovalStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    APPROVED = "approved", "已批准"


class DocumentTemplate(models.Model):
    code = models.CharField("模板编码", max_length=50)
    client_name = models.CharField("甲方名称", max_length=120, blank=True)
    business_type = models.CharField("业务类型", max_length=80, default=BUSINESS_TYPE)
    version = models.CharField("模板版本", max_length=50)
    document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="generation_templates",
        verbose_name="模板文件版本",
    )
    field_mapping = models.JSONField("字段映射", default=dict, blank=True)
    layout_schema = models.JSONField("结构化版式定义", default=dict, blank=True)
    section_order = models.JSONField("章节顺序", default=list)
    required_fact_fields = models.JSONField("必填事实字段", default=list)
    is_active = models.BooleanField("启用", default=False)
    approval_status = models.CharField(
        "审核状态",
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_generation_templates",
        verbose_name="审核人",
    )
    approved_at = models.DateTimeField("审核时间", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_generation_templates",
        verbose_name="创建人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["client_name", "code", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["code", "version"],
                name="docgen_template_code_ver_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["business_type", "is_active", "approval_status"],
                name="docgen_tpl_active_idx",
            ),
        ]
        verbose_name = "四措两案模板"
        verbose_name_plural = "四措两案模板"

    def __str__(self) -> str:
        return f"{self.code} {self.version}"


class ClauseBlock(models.Model):
    code = models.CharField("条款编码", max_length=80)
    version = models.CharField("条款版本", max_length=50)
    business_type = models.CharField("业务类型", max_length=80, default=BUSINESS_TYPE)
    section_code = models.CharField("章节编码", max_length=80)
    text = models.TextField("条款正文")
    risk_conditions = models.JSONField("风险适用条件", default=list)
    is_active = models.BooleanField("启用", default=False)
    approval_status = models.CharField(
        "审核状态",
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_generation_clauses",
        verbose_name="审核人",
    )
    approved_at = models.DateTimeField("审核时间", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_generation_clauses",
        verbose_name="创建人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["section_code", "code", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["code", "version"],
                name="docgen_clause_code_ver_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["business_type", "section_code", "is_active"],
                name="docgen_clause_lookup_idx",
            ),
        ]
        verbose_name = "四措两案批准条款"
        verbose_name_plural = "四措两案批准条款"

    def __str__(self) -> str:
        return f"{self.code} {self.version}"


class KnowledgeSection(models.Model):
    chunk_id = models.CharField("知识块编码", max_length=120, unique=True)
    source_document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="generation_knowledge_sections",
        verbose_name="来源文档版本",
    )
    business_type = models.CharField("业务类型", max_length=80, default=BUSINESS_TYPE)
    client_code = models.CharField("甲方编码", max_length=80, blank=True)
    section_code = models.CharField("章节编码", max_length=80)
    heading_path = models.JSONField("标题路径", default=list)
    paragraph_start = models.PositiveIntegerField("起始段落", default=0)
    paragraph_end = models.PositiveIntegerField("结束段落", default=0)
    locator = models.JSONField("来源定位", default=dict)
    text = models.TextField("正文")
    block_type = models.CharField("内容块类型", max_length=20, default="text")
    structured_content = models.JSONField("结构化内容", default=dict, blank=True)
    content_sha256 = models.CharField("正文SHA-256", max_length=64)
    component_tags = models.JSONField("部件标签", default=list)
    method_tags = models.JSONField("方法标签", default=list)
    risk_tags = models.JSONField("风险标签", default=list)
    embedding = models.JSONField("向量", default=list)
    embedding_model_alias = models.CharField("向量模型", max_length=120)
    embedding_dimension = models.PositiveIntegerField("向量维度")
    is_active = models.BooleanField("启用", default=False)
    approval_status = models.CharField(
        "审核状态",
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_generation_knowledge",
        verbose_name="审核人",
    )
    approved_at = models.DateTimeField("审核时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["business_type", "section_code", "chunk_id"]
        indexes = [
            models.Index(
                fields=["business_type", "section_code", "is_active"],
                name="docgen_knowledge_lookup_idx",
            ),
            models.Index(
                fields=["embedding_model_alias", "embedding_dimension"],
                name="docgen_knowledge_emb_idx",
            ),
        ]
        verbose_name = "四措两案知识章节"
        verbose_name_plural = "四措两案知识章节"

    def __str__(self) -> str:
        return self.chunk_id


class KnowledgeCorpusUpload(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "等待处理"
        PROCESSING = "processing", "正在处理"
        SUCCEEDED = "succeeded", "已入库"
        FAILED = "failed", "处理失败"

    class SectionCode(models.TextChoices):
        OVERVIEW = "overview", "工程概况与编制依据"
        ORGANIZATION_MEASURES = "organization_measures", "组织措施"
        CONSTRUCTION_PLAN = "construction_plan", "施工方案"
        TECHNICAL_MEASURES = "technical_measures", "技术措施"
        SAFETY_MEASURES = "safety_measures", "安全措施"
        RISK_IDENTIFICATION = "risk_identification", "风险辨识与预控"
        EMERGENCY_PLAN = "emergency_plan", "应急预案"
        ENVIRONMENTAL_MEASURES = "environmental_measures", "环境保护与文明施工"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="generation_corpus_uploads",
        verbose_name="来源文档版本",
    )
    business_type = models.CharField("业务类型", max_length=80, default=BUSINESS_TYPE)
    client_code = models.CharField("甲方编码", max_length=80, blank=True)
    section_code = models.CharField(
        "适用章节",
        max_length=80,
        choices=SectionCode.choices,
    )
    section_codes = models.JSONField("适用章节列表", default=list)
    indexed_section_codes = models.JSONField("已索引章节列表", default=list, blank=True)
    skipped_section_codes = models.JSONField("未识别章节列表", default=list, blank=True)
    fallback_to_full_document = models.BooleanField("允许整篇归入单一章节", default=False)
    component_tags = models.JSONField("部件标签", default=list, blank=True)
    method_tags = models.JSONField("方法标签", default=list, blank=True)
    risk_tags = models.JSONField("风险标签", default=list, blank=True)
    status = models.CharField(
        "处理状态",
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    chunk_count = models.PositiveIntegerField("知识块数量", default=0)
    embedding_model_alias = models.CharField("向量模型", max_length=120, blank=True)
    embedding_dimension = models.PositiveIntegerField("向量维度", null=True, blank=True)
    error_code = models.CharField("错误码", max_length=80, blank=True)
    error_message = models.CharField("错误说明", max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_generation_corpus_uploads",
        verbose_name="上传人",
    )
    started_at = models.DateTimeField("开始处理时间", null=True, blank=True)
    completed_at = models.DateTimeField("处理完成时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="docgen_corpus_status_idx"),
            models.Index(
                fields=["business_type", "section_code"],
                name="docgen_corpus_section_idx",
            ),
        ]
        verbose_name = "RAG语料上传"
        verbose_name_plural = "RAG语料上传"

    def __str__(self) -> str:
        return f"{self.source_document_version_id}:{self.section_code}"


class AgentSystemPrompt(models.Model):
    original_filename = models.CharField("原始文件名", max_length=255)
    version = models.CharField("版本", max_length=80)
    content = models.TextField("System Prompt正文")
    content_sha256 = models.CharField("正文SHA-256", max_length=64)
    is_active = models.BooleanField("当前启用", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_agent_system_prompts",
        verbose_name="上传人",
    )
    created_at = models.DateTimeField("上传时间", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["is_active", "-created_at"], name="docgen_sys_prompt_idx"),
        ]
        verbose_name = "Agent System Prompt"
        verbose_name_plural = "Agent System Prompts"

    def __str__(self) -> str:
        return f"{self.version}:{self.original_filename}"


class GenerationTask(models.Model):
    class Operation(models.TextChoices):
        EXTRACT = "extract", "提取事实"
        GENERATE = "generate", "生成文档"

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        EXTRACTING = "extracting", "提取事实"
        NEEDS_CONFIRMATION = "needs_confirmation", "待确认事实"
        READY = "ready", "可生成"
        QUEUED = "queued", "已排队"
        GENERATING = "generating", "生成中"
        REVIEW_REQUIRED = "review_required", "待审核"
        PENDING_APPROVAL = "pending_approval", "待批准"
        APPROVED = "approved", "已批准"
        EXPORTED = "exported", "已导出"
        FAILED = "failed", "失败"
        CANCELLED = "cancelled", "已停止"

    class CompletionState(models.TextChoices):
        COMPLETE = "complete", "内容完整"
        PENDING_MANUAL_FILL = "pending_manual_fill", "待人工补录"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="generation_tasks",
        verbose_name="项目",
    )
    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.PROTECT,
        related_name="generation_tasks",
        verbose_name="模板",
    )
    document_purpose = models.CharField(
        "文档用途",
        max_length=80,
        default=DOCUMENT_PURPOSE,
        editable=False,
    )
    business_type = models.CharField("业务类型", max_length=80, default=BUSINESS_TYPE)
    status = models.CharField(
        "状态",
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    operation = models.CharField(
        "当前操作",
        max_length=20,
        choices=Operation.choices,
        default=Operation.EXTRACT,
    )
    progress = models.PositiveSmallIntegerField("进度", default=0)
    completion_state = models.CharField(
        "内容完整状态",
        max_length=30,
        choices=CompletionState.choices,
        default=CompletionState.COMPLETE,
    )
    idempotency_key = models.CharField("创建幂等键", max_length=120)
    request_fingerprint = models.CharField("请求指纹", max_length=64)
    conversation_context = models.JSONField("会话上下文快照", default=dict)
    system_prompt = models.ForeignKey(
        AgentSystemPrompt,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="generation_tasks",
        verbose_name="System Prompt版本",
    )
    system_prompt_snapshot = models.TextField("System Prompt快照", blank=True)
    system_prompt_sha256 = models.CharField("System Prompt SHA-256", max_length=64, blank=True)
    facts_snapshot = models.JSONField("事实快照", default=list)
    fact_conflicts = models.JSONField("事实冲突", default=list)
    risk_profile = models.JSONField("风险画像", default=dict)
    pending_section_codes = models.JSONField("待生成章节", default=list)
    provider_alias = models.CharField("Provider", max_length=80, blank=True)
    model_alias = models.CharField("模型", max_length=120, blank=True)
    prompt_version = models.CharField("Prompt版本", max_length=80, blank=True)
    chunk_rule_version = models.CharField("切分规则版本", max_length=80, blank=True)
    generation_attempts = models.PositiveSmallIntegerField("生成尝试次数", default=0)
    error_code = models.CharField("错误码", max_length=80, blank=True)
    error_message = models.CharField("错误说明", max_length=500, blank=True)
    draft_storage_path = models.CharField("草稿存储路径", max_length=500, blank=True)
    draft_sha256 = models.CharField("草稿SHA-256", max_length=64, blank=True)
    draft_filename = models.CharField("草稿文件名", max_length=255, blank=True)
    output_document_version = models.ForeignKey(
        "documents.DocumentVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="generation_outputs",
        verbose_name="正式导出版本",
    )
    export_idempotency_key = models.CharField("导出幂等键", max_length=120, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_generation_tasks",
        verbose_name="创建人",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_generation_tasks",
        verbose_name="审核人",
    )
    approved_at = models.DateTimeField("批准时间", null=True, blank=True)
    started_at = models.DateTimeField("开始生成时间", null=True, blank=True)
    completed_at = models.DateTimeField("生成完成时间", null=True, blank=True)
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deleted_generation_tasks",
        verbose_name="删除人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["created_by", "idempotency_key"],
                name="docgen_task_actor_idem_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(document_purpose=DOCUMENT_PURPOSE),
                name="docgen_task_purpose_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(progress__gte=0, progress__lte=100),
                name="docgen_task_progress_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "status"], name="docgen_task_project_idx"),
            models.Index(fields=["status", "updated_at"], name="docgen_task_recovery_idx"),
        ]
        verbose_name = "四措两案生成任务"
        verbose_name_plural = "四措两案生成任务"

    def __str__(self) -> str:
        return f"{self.project_id}:{self.id}:{self.status}"


class GenerationTraceEvent(models.Model):
    class EventType(models.TextChoices):
        SYSTEM = "system", "系统"
        TOOL = "tool", "工具"
        MODEL = "model", "模型"
        RAG = "rag", "RAG"

    task = models.ForeignKey(
        GenerationTask,
        on_delete=models.CASCADE,
        related_name="workflow_events",
        verbose_name="生成任务",
    )
    sequence = models.PositiveIntegerField("序号")
    stage = models.CharField("业务阶段", max_length=50)
    event_type = models.CharField(
        "事件类型",
        max_length=20,
        choices=EventType.choices,
        default=EventType.SYSTEM,
    )
    tool = models.CharField("工具", max_length=100)
    status = models.CharField("状态", max_length=20)
    title = models.CharField("标题", max_length=160)
    detail = models.TextField("说明", blank=True)
    metadata = models.JSONField("结构化信息", default=dict, blank=True)
    created_at = models.DateTimeField("发生时间", auto_now_add=True)

    class Meta:
        ordering = ["sequence", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "sequence"],
                name="docgen_trace_task_seq_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["task", "sequence"],
                name="docgen_trace_task_idx",
            ),
        ]
        verbose_name = "四措两案工作流事件"
        verbose_name_plural = "四措两案工作流事件"

    def __str__(self) -> str:
        return f"{self.task_id}:{self.sequence}:{self.tool}:{self.status}"


class GenerationSource(models.Model):
    class ParseStatus(models.TextChoices):
        PENDING = "pending", "待解析"
        PARSED = "parsed", "已解析"
        FAILED = "failed", "解析失败"

    task = models.ForeignKey(
        GenerationTask,
        on_delete=models.CASCADE,
        related_name="sources",
        verbose_name="生成任务",
    )
    document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="generation_sources",
        verbose_name="来源文档版本",
    )
    file_sha256 = models.CharField("文件SHA-256", max_length=64)
    parse_status = models.CharField(
        "解析状态",
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.PENDING,
    )
    parse_error = models.CharField("解析错误", max_length=500, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "document_version"],
                name="docgen_source_task_ver_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["task", "parse_status"], name="docgen_source_parse_idx"),
        ]
        verbose_name = "四措两案生成来源"
        verbose_name_plural = "四措两案生成来源"

    def __str__(self) -> str:
        return f"{self.task_id}:{self.document_version_id}"


class ApprovedDocumentIllustration(models.Model):
    class Kind(models.TextChoices):
        HEIGHT_ESCAPE_PLAN = "height_escape_plan", "高空应急逃生预案图"
        HEIGHT_RESCUE_PLAN = "height_rescue_plan", "高空应急救援预案图"

    title = models.CharField("名称", max_length=160)
    kind = models.CharField("图片类型", max_length=40, choices=Kind.choices)
    document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="approved_generation_illustrations",
        verbose_name="图片文件版本",
    )
    caption = models.CharField("图注", max_length=300)
    alt_text = models.CharField("替代文本", max_length=300)
    applicability = models.JSONField("适用条件", default=dict, blank=True)
    width_px = models.PositiveIntegerField("像素宽度", default=0, editable=False)
    height_px = models.PositiveIntegerField("像素高度", default=0, editable=False)
    sha256 = models.CharField("图片SHA-256", max_length=64, blank=True, editable=False)
    is_active = models.BooleanField("启用", default=False)
    approval_status = models.CharField(
        "审核状态",
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_generation_illustrations",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_generation_illustrations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "title", "id"]
        indexes = [
            models.Index(
                fields=["kind", "is_active", "approval_status"],
                name="docgen_illus_active_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.kind}:{self.title}"


class GenerationTaskAsset(models.Model):
    class Kind(models.TextChoices):
        RESCUE_ROUTE = "rescue_route", "救援路线图"
        HEIGHT_ESCAPE_PLAN = "height_escape_plan", "高空应急逃生预案图"
        HEIGHT_RESCUE_PLAN = "height_rescue_plan", "高空应急救援预案图"

    task = models.ForeignKey(
        GenerationTask,
        on_delete=models.CASCADE,
        related_name="assets",
    )
    kind = models.CharField("图片类型", max_length=40, choices=Kind.choices)
    approved_illustration = models.ForeignKey(
        ApprovedDocumentIllustration,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="task_assets",
    )
    storage_path = models.CharField("存储路径", max_length=500)
    filename = models.CharField("文件名", max_length=255)
    media_type = models.CharField("媒体类型", max_length=80)
    sha256 = models.CharField("图片SHA-256", max_length=64)
    width_px = models.PositiveIntegerField("像素宽度")
    height_px = models.PositiveIntegerField("像素高度")
    caption = models.CharField("图注", max_length=300)
    alt_text = models.CharField("替代文本", max_length=300)
    metadata = models.JSONField("冻结信息", default=dict, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="confirmed_generation_assets",
    )
    confirmed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["task_id", "kind"]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "kind"],
                name="docgen_task_asset_kind_uq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.task_id}:{self.kind}"


class GeneratedSection(models.Model):
    task = models.ForeignKey(
        GenerationTask,
        on_delete=models.CASCADE,
        related_name="sections",
        verbose_name="生成任务",
    )
    section_code = models.CharField("章节编码", max_length=80)
    title = models.CharField("章节标题", max_length=255)
    content = models.TextField("可编辑正文")
    structured_content = models.JSONField("结构化正文", default=dict)
    citations = models.JSONField("引用", default=list)
    validation_issues = models.JSONField("校验问题", default=list)
    revision = models.PositiveIntegerField("修订号", default=1)
    is_locked = models.BooleanField("锁定", default=False)
    generated_at = models.DateTimeField("生成时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "section_code"],
                name="docgen_section_task_code_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["task", "is_locked"], name="docgen_section_lock_idx"),
        ]
        verbose_name = "四措两案生成章节"
        verbose_name_plural = "四措两案生成章节"

    def __str__(self) -> str:
        return f"{self.task_id}:{self.section_code}:r{self.revision}"


class GenerationReview(models.Model):
    class Action(models.TextChoices):
        FACTS_CONFIRMED = "facts_confirmed", "事实已确认"
        SECTION_EDITED = "section_edited", "章节已编辑"
        SECTION_LOCKED = "section_locked", "章节已锁定"
        SECTION_UNLOCKED = "section_unlocked", "章节已解锁"
        SECTION_REGENERATED = "section_regenerated", "章节重新生成"
        SUBMITTED = "submitted", "提交审核"
        APPROVED = "approved", "批准"
        EXPORTED = "exported", "导出"
        RETRIED = "retried", "重试"
        STOPPED = "stopped", "停止"

    task = models.ForeignKey(
        GenerationTask,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="生成任务",
    )
    section = models.ForeignKey(
        GeneratedSection,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviews",
        verbose_name="章节",
    )
    action = models.CharField("动作", max_length=40, choices=Action.choices)
    comment = models.TextField("意见", blank=True)
    metadata = models.JSONField("附加信息", default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="generation_reviews",
        verbose_name="操作人",
    )
    created_at = models.DateTimeField("操作时间", auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["task", "action"], name="docgen_review_action_idx"),
        ]
        verbose_name = "四措两案审核记录"
        verbose_name_plural = "四措两案审核记录"

    def __str__(self) -> str:
        return f"{self.task_id}:{self.action}:{self.actor_id}"
