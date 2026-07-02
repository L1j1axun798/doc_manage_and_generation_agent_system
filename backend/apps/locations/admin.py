from django.contrib import admin

from .models import LocationReport


@admin.register(LocationReport)
class LocationReportAdmin(admin.ModelAdmin):
    list_display = ("user", "report_status", "reported_at", "accuracy")
    list_filter = ("report_status", "reported_at")
    search_fields = ("user__username", "user__real_name", "address", "failure_reason")
    readonly_fields = ("created_at",)
