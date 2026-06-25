from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_real_name = serializers.CharField(source="user.real_name", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user",
            "user_username",
            "user_real_name",
            "action",
            "resource_type",
            "resource_id",
            "result",
            "ip_address",
            "user_agent",
            "request_id",
            "before_data",
            "after_data",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields
