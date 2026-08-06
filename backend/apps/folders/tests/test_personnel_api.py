import pytest
from django.contrib.auth import get_user_model

from apps.audit.models import AuditLog

from ..models import Folder, PersonnelProfile

User = get_user_model()


def make_user(username: str, role: str):
    return User.objects.create_user(
        username=username,
        password="Password123!",
        real_name=username,
        role=role,
    )


@pytest.mark.django_db
def test_admin_can_list_and_update_public_staff_personnel(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    staff_root = Folder.objects.create(
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=True,
        created_by=admin,
    )
    person = Folder.objects.create(parent=staff_root, name="张三", created_by=admin)
    Folder.objects.create(parent=person, name="身份证", created_by=admin)
    other_root = Folder.objects.create(
        name="公司资质",
        code="PUBLIC-COMPANY",
        is_system_root=True,
        created_by=admin,
    )
    Folder.objects.create(parent=other_root, name="示例公司", created_by=admin)
    client.force_login(admin)

    list_response = client.get("/api/v1/personnel/")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1
    assert list_response.json()["results"][0] == {
        "id": str(person.pk),
        "folder_id": person.pk,
        "name": "张三",
        "gender": "unknown",
        "gender_display": "未填写",
        "id_card_number": "",
        "phone": "",
        "profile_complete": False,
        "updated_at": None,
    }

    update_response = client.patch(
        f"/api/v1/personnel/{person.pk}/",
        {
            "gender": "male",
            "id_card_number": "110101199001010011",
            "phone": "138-0000-0000",
        },
        content_type="application/json",
    )
    assert update_response.status_code == 200
    assert update_response.json()["gender_display"] == "男"
    assert update_response.json()["id_card_number"] == "110101199001010011"
    assert update_response.json()["phone"] == "13800000000"
    assert update_response.json()["profile_complete"] is True
    profile = PersonnelProfile.objects.get(folder=person)
    assert profile.updated_by == admin
    audit = AuditLog.objects.get(action="personnel.update", resource_id=str(profile.pk))
    assert "id_card_number" not in audit.after_data
    assert "phone" not in audit.after_data


@pytest.mark.django_db
def test_personnel_api_is_system_admin_only(client):
    user = make_user("operator", User.Role.DATA_OPERATOR)
    client.force_login(user)
    assert client.get("/api/v1/personnel/").status_code == 403
