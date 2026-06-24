from django.contrib import admin

from .models import DocumentGrant


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
