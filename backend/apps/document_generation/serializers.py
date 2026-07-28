from __future__ import annotations

from rest_framework import serializers

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
    KnowledgeSection,
)


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
            "approved_rag_source_files": knowledge.values(
                "source_document_version_id"
            ).distinct().count(),
            "approved_clause_blocks": ClauseBlock.objects.filter(
                business_type=obj.business_type,
                is_active=True,
                approval_status=ApprovalStatus.APPROVED,
            ).count(),
            "used_rag_citations": sum(len(section.citations) for section in obj.sections.all()),
        }


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


class ReviewActionSerializer(serializers.Serializer):
    comment = serializers.CharField(
        required=False,
        default="",
        allow_blank=True,
        max_length=2000,
    )


class ExportSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(max_length=120)


class TraceEventQuerySerializer(serializers.Serializer):
    after_sequence = serializers.IntegerField(
        min_value=0,
        required=False,
        default=0,
    )
