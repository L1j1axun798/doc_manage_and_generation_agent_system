from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


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
