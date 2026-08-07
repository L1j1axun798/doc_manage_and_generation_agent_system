from django.contrib import admin

from .models import (
    AgentSystemPrompt,
    ClauseBlock,
    DocumentTemplate,
    GeneratedSection,
    GenerationReview,
    GenerationSource,
    GenerationTask,
    KnowledgeSection,
)


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
