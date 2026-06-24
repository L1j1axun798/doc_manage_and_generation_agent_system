from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Project, ProjectMember

User = get_user_model()


class ProjectSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source="manager.real_name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.real_name", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "code",
            "description",
            "manager",
            "manager_name",
            "status",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "archived_at",
            "archived_by",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "archived_at",
            "archived_by",
        ]


class ProjectMemberSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_real_name = serializers.CharField(source="user.real_name", read_only=True)

    class Meta:
        model = ProjectMember
        fields = [
            "id",
            "project",
            "user",
            "user_username",
            "user_real_name",
            "role",
            "can_upload",
            "can_download_restricted",
            "can_manage_folder",
            "can_delete",
            "can_restore",
            "can_manage_permission",
            "joined_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "user_username",
            "user_real_name",
            "joined_at",
        ]

    def validate_user(self, user: Any) -> Any:
        if not user.is_active:
            raise serializers.ValidationError("不能添加已停用用户")
        project = self.context.get("project")
        if (
            project is not None
            and self.instance is None
            and ProjectMember.objects.filter(project=project, user=user).exists()
        ):
            raise serializers.ValidationError("该用户已是项目成员")
        return user
