from rest_framework import serializers

from .models import Folder, PersonnelProfile
from .personnel import personnel_snapshot


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


class PersonnelRecordSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    folder_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    gender = serializers.SerializerMethodField()
    gender_display = serializers.SerializerMethodField()
    id_card_number = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    profile_complete = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    def _snapshot(self, obj: Folder) -> dict:
        return personnel_snapshot(obj)

    def get_id(self, obj: Folder) -> str:
        return str(obj.pk)

    def get_folder_id(self, obj: Folder) -> int:
        return obj.pk

    def get_name(self, obj: Folder) -> str:
        return obj.name

    def get_gender(self, obj: Folder) -> str:
        return str(self._snapshot(obj)["gender"])

    def get_gender_display(self, obj: Folder) -> str:
        return str(self._snapshot(obj)["gender_display"])

    def get_id_card_number(self, obj: Folder) -> str:
        return str(self._snapshot(obj)["id_card_number"])

    def get_phone(self, obj: Folder) -> str:
        return str(self._snapshot(obj)["phone"])

    def get_profile_complete(self, obj: Folder) -> bool:
        return bool(self._snapshot(obj)["profile_complete"])

    def get_updated_at(self, obj: Folder) -> object:
        return self._snapshot(obj)["updated_at"]


class PersonnelRecordUpdateSerializer(serializers.Serializer):
    gender = serializers.ChoiceField(choices=PersonnelProfile.Gender.choices, required=False)
    id_card_number = serializers.CharField(
        max_length=32,
        allow_blank=True,
        trim_whitespace=True,
        required=False,
    )
    phone = serializers.CharField(
        max_length=30,
        allow_blank=True,
        trim_whitespace=True,
        required=False,
    )
