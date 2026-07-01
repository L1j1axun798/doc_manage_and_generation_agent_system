from django.contrib import admin

from .models import Project, ProjectMember


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "manager", "status", "created_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("code", "name", "manager__username", "manager__real_name")
    autocomplete_fields = ("manager", "created_by", "archived_by")
    inlines = [ProjectMemberInline]


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "role", "can_manage_permission", "joined_at")
    list_filter = ("role", "can_manage_permission", "joined_at")
    search_fields = ("project__code", "project__name", "user__username", "user__real_name")
    autocomplete_fields = ("project", "user")
