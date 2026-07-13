from rest_framework import serializers

from .models import SystemBackupRun


class SystemBackupRunSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    created_by_real_name = serializers.CharField(source="created_by.real_name", read_only=True)
    offsite_available = serializers.SerializerMethodField()
    local_available = serializers.SerializerMethodField()
    error_summary = serializers.SerializerMethodField()

    class Meta:
        model = SystemBackupRun
        fields = [
            "id",
            "trigger",
            "status",
            "started_at",
            "finished_at",
            "local_available",
            "offsite_available",
            "sha256",
            "size_bytes",
            "error_summary",
            "created_by",
            "created_by_username",
            "created_by_real_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_offsite_available(self, obj: SystemBackupRun) -> bool:
        return bool(obj.status == SystemBackupRun.Status.SUCCESS and obj.offsite_path)

    def get_local_available(self, obj: SystemBackupRun) -> bool:
        return bool(obj.status == SystemBackupRun.Status.SUCCESS and obj.local_path)

    def get_error_summary(self, obj: SystemBackupRun) -> str:
        return "备份失败，请查看服务器日志" if obj.error_message else ""
