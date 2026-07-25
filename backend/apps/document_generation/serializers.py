from __future__ import annotations

from rest_framework import serializers

from .models import (
    BUSINESS_TYPE,
    DOCUMENT_PURPOSE,
    DocumentTemplate,
    GeneratedSection,
    GenerationReview,
    GenerationSource,
    GenerationTask,
)


class DocumentTemplateSerializer(serializers.ModelSerializer):
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
            "business_type",
            "version",
            "document_version_id",
            "filename",
            "field_mapping",
            "section_order",
            "required_fact_fields",
        ]


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
        ]

    def get_template_name(self, obj: GenerationTask) -> str:
        return f"{obj.template.code} {obj.template.version}"


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
