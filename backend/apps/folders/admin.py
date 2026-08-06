from django.contrib import admin

from .models import Folder, PersonnelProfile


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "project",
        "parent",
        "code",
        "sort_order",
        "is_active",
        "is_system_root",
        "created_at",
    )
    list_filter = ("is_active", "is_system_root", "project", "created_at")
    search_fields = ("name", "code", "project__name", "project__code")
    autocomplete_fields = ("project", "parent", "created_by")
    readonly_fields = ("is_system_root",)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_system_root:
            return tuple(field.name for field in obj._meta.fields)
        return super().get_readonly_fields(request, obj)


@admin.register(PersonnelProfile)
class PersonnelProfileAdmin(admin.ModelAdmin):
    list_display = ("folder", "gender", "phone", "updated_by", "updated_at")
    list_filter = ("gender", "updated_at")
    search_fields = ("folder__name", "id_card_number", "phone")
    autocomplete_fields = ("folder", "updated_by")
