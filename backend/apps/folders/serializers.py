from rest_framework import serializers

from .models import Folder


class FolderSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source="created_by.real_name", read_only=True)

    class Meta:
        model = Folder
        fields = [
            "id",
            "project",
            "project_name",
            "parent",
            "parent_name",
            "name",
            "code",
            "sort_order",
            "is_active",
            "is_system_root",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_active",
            "is_system_root",
            "parent_name",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]


class FolderMoveSerializer(serializers.Serializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.filter(is_active=True),
        allow_null=True,
        required=False,
    )  # type: ignore[assignment]
    sort_order = serializers.IntegerField(min_value=0, required=False)
