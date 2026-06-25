from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "category",
            "resource_type",
            "resource_id",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields
