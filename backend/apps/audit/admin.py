from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "result", "user", "resource_type", "resource_id", "created_at")
    list_filter = ("action", "result", "created_at")
    search_fields = ("action", "resource_type", "resource_id", "request_id", "user__username")
    readonly_fields = [field.name for field in AuditLog._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
