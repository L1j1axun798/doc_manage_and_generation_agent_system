from __future__ import annotations

from rest_framework import serializers

from common.validators import uploaded_file_extension, validate_uploaded_file

from .models import (
    BUSINESS_TYPE,
    DOCUMENT_PURPOSE,
    ApprovalStatus,
    ClauseBlock,
    DocumentTemplate,
    GeneratedSection,
    GenerationReview,
    GenerationSource,
    GenerationTask,
    GenerationTraceEvent,
    KnowledgeCorpusUpload,
    KnowledgeSection,
)

KNOWLEDGE_CORPUS_MAX_BYTES = 20 * 1024 * 1024
CLIENT_TEMPLATE_MAX_BYTES = 20 * 1024 * 1024


def document_template_display_name(template: DocumentTemplate) -> str:
    mapped_name = template.field_mapping.get("template_name")
    if isinstance(mapped_name, str) and mapped_name.strip():
        return mapped_name.strip()
    if template.client_name.strip():
        return template.client_name.strip()
    return template.document_version.original_filename


class DocumentTemplateSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    document_version_id = serializers.IntegerField(read_only=True)
    filename = serializers.CharField(
        source="document_version.original_filename",
        read_only=True,
    )

    class Meta:
        model = DocumentTemplate
        fields = [
            "id",
            "code",
            "client_name",
            "display_name",
            "business_type",
            "version",
            "document_version_id",
            "filename",
            "field_mapping",
            "section_order",
            "required_fact_fields",
        ]

    def get_display_name(self, obj: DocumentTemplate) -> str:
        return document_template_display_name(obj)


class ClientTemplateUploadSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(min_value=1)
    file = serializers.FileField(write_only=True)

    def validate_file(self, uploaded_file):
        validate_uploaded_file(uploaded_file)
        if uploaded_file_extension(uploaded_file) != ".docx":
            raise serializers.ValidationError("甲方模板仅支持 DOCX 文件")
        if uploaded_file.size > CLIENT_TEMPLATE_MAX_BYTES:
            raise serializers.ValidationError("甲方模板不能超过 20 MB")
        return uploaded_file


class ClientTemplateSelectSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(min_value=1)


class KnowledgeCorpusUploadSerializer(serializers.ModelSerializer):
    filename = serializers.CharField(
        source="source_document_version.original_filename",
        read_only=True,
    )
    file_sha256 = serializers.CharField(
        source="source_document_version.sha256",
        read_only=True,
    )
    created_by_name = serializers.CharField(source="created_by.real_name", read_only=True)
    section_names = serializers.SerializerMethodField()
    indexed_section_names = serializers.SerializerMethodField()
    skipped_section_names = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeCorpusUpload
        fields = [
            "id",
            "filename",
            "file_sha256",
            "business_type",
            "section_codes",
            "section_names",
            "indexed_section_codes",
            "indexed_section_names",
            "skipped_section_codes",
            "skipped_section_names",
            "status",
            "chunk_count",
            "embedding_model_alias",
            "embedding_dimension",
            "error_code",
            "error_message",
            "created_by_name",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_section_names(self, upload: KnowledgeCorpusUpload) -> list[str]:
        return _section_names(upload.section_codes or [upload.section_code])

    def get_indexed_section_names(self, upload: KnowledgeCorpusUpload) -> list[str]:
        return _section_names(upload.indexed_section_codes)

    def get_skipped_section_names(self, upload: KnowledgeCorpusUpload) -> list[str]:
        return _section_names(upload.skipped_section_codes)


class KnowledgeCorpusUploadCreateSerializer(serializers.Serializer):
    file = serializers.FileField()
    section_codes = serializers.ListField(
        child=serializers.ChoiceField(choices=KnowledgeCorpusUpload.SectionCode.choices),
        allow_empty=False,
        max_length=len(KnowledgeCorpusUpload.SectionCode.choices),
    )

    def validate_file(self, uploaded_file):
        validate_uploaded_file(uploaded_file)
        if uploaded_file_extension(uploaded_file) not in {".docx", ".pdf"}:
            raise serializers.ValidationError("RAG语料仅支持可解析的 DOCX 或文本型 PDF")
        if uploaded_file.size > KNOWLEDGE_CORPUS_MAX_BYTES:
            raise serializers.ValidationError("单个RAG语料文件不能超过20MB")
        return uploaded_file

    def validate_section_codes(self, values):
        return list(dict.fromkeys(values))


class RagSectionCoverageSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=KnowledgeCorpusUpload.SectionCode.choices)
    name = serializers.CharField()
    chunk_count = serializers.IntegerField(min_value=0)


class RagOperationsSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["healthy", "processing", "attention"])
    redis_status = serializers.ChoiceField(choices=["ok", "unavailable"])
    worker_status = serializers.ChoiceField(choices=["idle", "busy", "offline", "unknown"])
    queue_depth = serializers.IntegerField(min_value=0)
    processing_uploads = serializers.IntegerField(min_value=0)
    failed_uploads = serializers.IntegerField(min_value=0)
    latest_upload_status = serializers.ChoiceField(
        choices=KnowledgeCorpusUpload.Status.choices,
        allow_null=True,
    )
    latest_upload_at = serializers.DateTimeField(allow_null=True)


class RagOverviewSerializer(serializers.Serializer):
    knowledge_status = serializers.ChoiceField(choices=["ready", "empty"])
    knowledge_chunks = serializers.IntegerField(min_value=0)
    source_documents = serializers.IntegerField(min_value=0)
    covered_section_count = serializers.IntegerField(min_value=0)
    total_section_count = serializers.IntegerField(min_value=0)
    section_coverage = RagSectionCoverageSerializer(many=True)
    last_indexed_at = serializers.DateTimeField(allow_null=True)
    embedding_model_alias = serializers.CharField()
    embedding_dimension = serializers.IntegerField(min_value=1)
    operations = RagOperationsSerializer(allow_null=True)


def _section_names(section_codes: list[str]) -> list[str]:
    labels = dict(KnowledgeCorpusUpload.SectionCode.choices)
    return [labels[code] for code in section_codes if code in labels]


class GenerationSourceSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(
        source="document_version.document.title",
        read_only=True,
    )
    filename = serializers.CharField(
        source="document_version.original_filename",
        read_only=True,
    )

    class Meta:
        model = GenerationSource
        fields = [
            "id",
            "document_version_id",
            "document_title",
            "filename",
            "file_sha256",
            "parse_status",
            "parse_error",
            "created_at",
        ]


class GeneratedSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedSection
        fields = [
            "section_code",
            "title",
            "content",
            "structured_content",
            "citations",
            "validation_issues",
            "revision",
            "is_locked",
            "generated_at",
            "updated_at",
        ]


class GenerationReviewSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.real_name", read_only=True)
    section_code = serializers.CharField(source="section.section_code", read_only=True)

    class Meta:
        model = GenerationReview
        fields = [
            "id",
            "section_code",
            "action",
            "comment",
            "metadata",
            "actor_name",
            "created_at",
        ]


class GenerationTraceEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationTraceEvent
        fields = [
            "sequence",
            "stage",
            "event_type",
            "tool",
            "status",
            "title",
            "detail",
            "metadata",
            "created_at",
        ]


class GenerationTaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    template_name = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source="created_by.real_name", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.real_name", read_only=True)
    output_document_id = serializers.IntegerField(
        source="output_document_version.document_id",
        read_only=True,
    )
    sources = GenerationSourceSerializer(many=True, read_only=True)
    sections = GeneratedSectionSerializer(many=True, read_only=True)
    reviews = GenerationReviewSerializer(many=True, read_only=True)
    reference_summary = serializers.SerializerMethodField()

    class Meta:
        model = GenerationTask
        fields = [
            "id",
            "project_id",
            "project_name",
            "template_id",
            "template_name",
            "document_purpose",
            "business_type",
            "status",
            "operation",
            "progress",
            "conversation_context",
            "facts_snapshot",
            "fact_conflicts",
            "risk_profile",
            "pending_section_codes",
            "provider_alias",
            "model_alias",
            "prompt_version",
            "chunk_rule_version",
            "generation_attempts",
            "error_code",
            "error_message",
            "output_document_version_id",
            "output_document_id",
            "created_by_name",
            "reviewed_by_name",
            "approved_at",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "sources",
            "sections",
            "reviews",
            "reference_summary",
        ]

    def get_template_name(self, obj: GenerationTask) -> str:
        return document_template_display_name(obj.template)

    def get_reference_summary(self, obj: GenerationTask) -> dict[str, int]:
        knowledge = KnowledgeSection.objects.filter(
            business_type=obj.business_type,
            is_active=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        return {
            "project_source_files": len(obj.sources.all()),
            "approved_rag_chunks": knowledge.count(),
            "approved_rag_source_files": knowledge.values("source_document_version_id")
            .distinct()
            .count(),
            "approved_clause_blocks": ClauseBlock.objects.filter(
                business_type=obj.business_type,
                is_active=True,
                approval_status=ApprovalStatus.APPROVED,
            ).count(),
            "used_rag_citations": sum(len(section.citations) for section in obj.sections.all()),
        }


class GenerationConversationContextSerializer(serializers.Serializer):
    initial_message = serializers.CharField(
        required=False,
        default="",
        allow_blank=True,
        trim_whitespace=True,
        max_length=4000,
    )
    selected_personnel_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
        allow_empty=True,
        max_length=50,
    )

    def validate_selected_personnel_ids(self, values: list[int]) -> list[int]:
        if len(values) != len(set(values)):
            raise serializers.ValidationError("所选人员不能重复")
        return values


class AvailablePersonnelQuerySerializer(serializers.Serializer):
    project_id = serializers.IntegerField(min_value=1)


class GenerationTaskCreateSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(min_value=1)
    template_id = serializers.IntegerField(min_value=1)
    document_purpose = serializers.ChoiceField(
        choices=[DOCUMENT_PURPOSE],
        default=DOCUMENT_PURPOSE,
    )
    business_type = serializers.ChoiceField(
        choices=[BUSINESS_TYPE],
        default=BUSINESS_TYPE,
    )
    idempotency_key = serializers.CharField(max_length=120)
    facts = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
        allow_empty=True,
    )
    conversation_context = GenerationConversationContextSerializer(
        required=False,
        default=dict,
    )


class GenerationPipelineCreateSerializer(GenerationTaskCreateSerializer):
    document_version_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=50,
    )


class GenerationSourceAddSerializer(serializers.Serializer):
    document_version_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=50,
    )


class GenerationFactConfirmSerializer(serializers.Serializer):
    facts = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=100,
    )


class GeneratedSectionUpdateSerializer(serializers.Serializer):
    content = serializers.CharField(trim_whitespace=True, allow_blank=False)
    expected_revision = serializers.IntegerField(min_value=1)


class SectionLockSerializer(serializers.Serializer):
    locked = serializers.BooleanField(default=True)


class SectionRegenerateSerializer(serializers.Serializer):
    instruction = serializers.CharField(
        trim_whitespace=True,
        allow_blank=False,
        max_length=4000,
    )
    rag_chunk_ids = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
        default=list,
        max_length=8,
    )

    def validate_rag_chunk_ids(self, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise serializers.ValidationError("RAG片段不能重复选择")
        return cleaned


class ReviewActionSerializer(serializers.Serializer):
    comment = serializers.CharField(
        required=False,
        default="",
        allow_blank=True,
        max_length=2000,
    )


class ExportSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(max_length=120)
    filename = serializers.CharField(max_length=255, required=False)


class GenerationExportInfoSerializer(serializers.Serializer):
    target_folder = serializers.CharField()
    agent_generated_count = serializers.IntegerField(min_value=0)
    default_filename = serializers.CharField()


class TraceEventQuerySerializer(serializers.Serializer):
    after_sequence = serializers.IntegerField(
        min_value=0,
        required=False,
        default=0,
    )
