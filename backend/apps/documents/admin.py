from django.contrib import admin

from .models import Document, DocumentVersion


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "project", "folder", "current_version", "created_by"]
    list_filter = ["project"]
    search_fields = ["title"]


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "document",
        "version_number",
        "original_filename",
        "file_size",
        "sha256",
        "uploaded_by",
    ]
    search_fields = ["original_filename", "sha256"]
