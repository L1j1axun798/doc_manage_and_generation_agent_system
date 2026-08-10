from django.contrib import admin

from .models import (
    AgentSystemPrompt,
    ApprovedDocumentIllustration,
    ClauseBlock,
    DocumentTemplate,
    GeneratedSection,
    GenerationReview,
    GenerationSource,
    GenerationTask,
    GenerationTaskAsset,
    KnowledgeSection,
)
from .image_assets import normalize_document_image
from common.storage import LocalDocumentStorage


@admin.register(AgentSystemPrompt)
class AgentSystemPromptAdmin(admin.ModelAdmin):
    list_display = ("version", "original_filename", "is_active", "created_by", "created_at")
    list_filter = ("is_active",)
    search_fields = ("version", "original_filename", "content_sha256")


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "client_name", "approval_status", "is_active")
    list_filter = ("approval_status", "is_active", "business_type")
    search_fields = ("code", "client_name", "version")


@admin.register(ClauseBlock)
class ClauseBlockAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "section_code", "approval_status", "is_active")
    list_filter = ("approval_status", "is_active", "section_code")
    search_fields = ("code", "text")


@admin.register(KnowledgeSection)
class KnowledgeSectionAdmin(admin.ModelAdmin):
    list_display = ("chunk_id", "section_code", "approval_status", "is_active")
    list_filter = ("approval_status", "is_active", "section_code")
    search_fields = ("chunk_id", "text")


admin.site.register(GenerationTask)
admin.site.register(GenerationSource)
admin.site.register(GeneratedSection)
admin.site.register(GenerationReview)
admin.site.register(GenerationTaskAsset)


@admin.register(ApprovedDocumentIllustration)
class ApprovedDocumentIllustrationAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "approval_status", "is_active", "width_px", "height_px")
    list_filter = ("kind", "approval_status", "is_active")
    search_fields = ("title", "caption", "alt_text")

    def save_model(self, request, obj, form, change):
        path = LocalDocumentStorage().resolve(obj.document_version.storage_path)
        source_content = path.read_bytes()
        _normalized, _media_type, width, height = normalize_document_image(source_content)
        obj.width_px = width
        obj.height_px = height
        from hashlib import sha256

        obj.sha256 = sha256(source_content).hexdigest()
        if not obj.created_by_id:
            obj.created_by = request.user
        if obj.approval_status == "approved":
            obj.approved_by = request.user
            from django.utils import timezone

            obj.approved_at = timezone.now()
        super().save_model(request, obj, form, change)
