from django.contrib import admin

from .models import DocumentGrant, TemporaryAccessGrant


@admin.register(DocumentGrant)
class DocumentGrantAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "document",
        "user",
        "can_view",
        "can_download",
        "can_manage",
        "expires_at",
        "revoked_at",
    ]
    list_filter = ["can_view", "can_download", "can_manage", "revoked_at"]
    search_fields = ["document__title", "user__username", "user__real_name"]


@admin.register(TemporaryAccessGrant)
class TemporaryAccessGrantAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "document_version",
        "max_downloads",
        "used_count",
        "expires_at",
        "revoked_at",
        "last_used_at",
    ]
    list_filter = ["revoked_at", "expires_at"]
    search_fields = ["document_version__document__title", "token_hash"]
