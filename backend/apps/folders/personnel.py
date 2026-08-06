from __future__ import annotations

import re
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from rest_framework.exceptions import ValidationError

from apps.audit.services import audit_log

from .defaults import standard_root_for_code
from .models import Folder, PersonnelProfile


def personnel_folders() -> QuerySet[Folder]:
    definition = standard_root_for_code("PUBLIC-STAFF")
    if definition is None:
        return Folder.objects.none()
    return (
        Folder.objects.filter(
            project__isnull=True,
            parent__project__isnull=True,
            parent__parent__isnull=True,
            parent__is_active=True,
            is_active=True,
        )
        .filter(Q(parent__code=definition.code) | Q(parent__name__in=definition.names))
        .select_related("parent", "personnel_profile", "personnel_profile__updated_by")
        .order_by("sort_order", "id")
    )


def personnel_profile_for(folder: Folder) -> PersonnelProfile | None:
    try:
        return folder.personnel_profile
    except PersonnelProfile.DoesNotExist:
        return None


def personnel_snapshot(folder: Folder) -> dict[str, Any]:
    profile = personnel_profile_for(folder)
    return {
        "id": str(folder.pk),
        "name": folder.name.strip(),
        "gender": profile.gender if profile else PersonnelProfile.Gender.UNKNOWN,
        "gender_display": profile.get_gender_display() if profile else "未填写",
        "id_card_number": profile.id_card_number if profile else "",
        "phone": profile.phone if profile else "",
        "profile_complete": bool(
            profile
            and profile.gender != PersonnelProfile.Gender.UNKNOWN
            and profile.id_card_number
            and profile.phone
        ),
        "updated_at": profile.updated_at if profile else None,
    }


def normalize_id_card_number(value: str) -> str:
    normalized = value.strip().upper().replace(" ", "")
    if normalized and not re.fullmatch(r"\d{17}[0-9X]", normalized):
        raise ValidationError({"id_card_number": "身份证号应为18位，末位可以是X"})
    return normalized


def normalize_phone(value: str) -> str:
    normalized = re.sub(r"[\s-]", "", value.strip())
    if normalized and not re.fullmatch(r"\+?\d{7,20}", normalized):
        raise ValidationError({"phone": "手机号格式不正确"})
    return normalized


@transaction.atomic
def update_personnel_profile(
    *,
    actor: Any,
    folder: Folder,
    data: dict[str, Any],
    request: Any = None,
) -> PersonnelProfile:
    locked_folder = personnel_folders().select_for_update().filter(pk=folder.pk).first()
    if locked_folder is None:
        raise ValidationError("只有“人员资质”下的启用一级人员目录可以维护人员信息")
    before = personnel_snapshot(locked_folder)
    profile, _ = PersonnelProfile.objects.select_for_update().get_or_create(folder=locked_folder)
    profile.gender = data.get("gender", profile.gender)
    profile.id_card_number = normalize_id_card_number(
        data.get("id_card_number", profile.id_card_number)
    )
    profile.phone = normalize_phone(data.get("phone", profile.phone))
    profile.updated_by = actor
    profile.save()
    after = {
        "gender": profile.gender,
        "id_card_number": profile.id_card_number,
        "phone": profile.phone,
    }
    audit_log(
        user=actor,
        action="personnel.update",
        result="success",
        request=request,
        resource=profile,
        before_data={
            "folder_id": locked_folder.pk,
            "gender": before["gender"],
            "has_id_card_number": bool(before["id_card_number"]),
            "has_phone": bool(before["phone"]),
        },
        after_data={
            "folder_id": locked_folder.pk,
            "gender": after["gender"],
            "has_id_card_number": bool(after["id_card_number"]),
            "has_phone": bool(after["phone"]),
        },
    )
    return profile
