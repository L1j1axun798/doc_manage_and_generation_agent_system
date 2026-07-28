import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.access.models import DocumentGrant
from apps.documents.models import Document
from apps.folders.models import Folder
from apps.notifications.models import Notification
from apps.projects.models import Project, ProjectMember

User = get_user_model()


@pytest.mark.django_db
def test_seed_dev_data_creates_idempotent_frontend_fixture(settings, tmp_path):
    settings.DEBUG = True
    settings.FILE_STORAGE_ROOT = tmp_path

    call_command("seed_dev_data")
    call_command("seed_dev_data")

    assert User.objects.filter(username__in=["admin", "manager", "operator", "viewer"]).count() == 4
    assert Project.objects.filter(code="DEMO-FRONTEND").count() == 1
    project = Project.objects.get(code="DEMO-FRONTEND")
    assert ProjectMember.objects.filter(project=project).count() == 3
    assert Folder.objects.filter(project=project, name="入场前置资料").count() == 1
    assert Document.objects.filter(title="机组叶片检测报告").count() == 1
    assert Document.objects.filter(title="缺陷复核记录").count() == 1
    assert DocumentGrant.objects.filter(document__title="缺陷复核记录").count() == 1
    assert Notification.objects.filter(title="示例项目已准备").count() == 1
    assert [path for path in tmp_path.rglob("*") if path.is_file()]
