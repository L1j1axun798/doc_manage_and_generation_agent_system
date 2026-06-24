from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.audit.services import audit_log

from .models import User
from .services import user_snapshot


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "业务信息",
            {
                "fields": (
                    "real_name",
                    "employee_no",
                    "role",
                    "phone",
                    "must_change_password",
                )
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "业务信息",
            {
                "fields": (
                    "real_name",
                    "employee_no",
                    "role",
                    "phone",
                    "must_change_password",
                )
            },
        ),
    )
    list_display = (
        "username",
        "real_name",
        "employee_no",
        "role",
        "is_active",
        "must_change_password",
        "is_staff",
    )
    list_filter = ("role", "is_active", "must_change_password", "is_staff", "is_superuser")
    search_fields = ("username", "real_name", "employee_no", "phone", "email")

    def save_model(self, request, obj, form, change) -> None:
        before_data = None
        if change and obj.pk:
            before_data = user_snapshot(type(obj).objects.get(pk=obj.pk))
        super().save_model(request, obj, form, change)
        audit_log(
            user=request.user,
            action="user.update" if change else "user.create",
            resource=obj,
            result="success",
            request=request,
            before_data=before_data,
            after_data=user_snapshot(obj),
        )
