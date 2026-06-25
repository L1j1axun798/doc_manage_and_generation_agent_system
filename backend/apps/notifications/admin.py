from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "recipient", "title", "category", "is_read", "created_at"]
    list_filter = ["category", "is_read", "created_at"]
    search_fields = ["title", "message", "recipient__username", "recipient__real_name"]
