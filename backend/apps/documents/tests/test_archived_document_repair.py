import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from apps.documents.models import Document
from apps.documents.repair import repair_archived_document_folders
from apps.documents.views import descendant_folder_ids
from apps.folders.models import Folder
from apps.projects.models import Project
from apps.projects.services import archive_project_folders

User = get_user_model()


def make_user(username: str, role: str):
    return User.objects.create_user(
        username=username,
        password="Password123!",
        real_name=username,
        role=role,
    )


@pytest.mark.django_db
def test_repair_archived_document_folder_moves_document_pointer_into_archive_year_tree():
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    archived_project = Project.objects.create(
        name="归档项目",
        code="P002",
        created_by=admin,
        archived_by=admin,
        archived_at=timezone.now(),
        status=Project.Status.ARCHIVED,
    )
    other_project = Project.objects.create(name="其他项目", code="P001", created_by=admin)
    public_staff_root = Folder.objects.create(
        project=None,
        parent=None,
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=True,
        created_by=admin,
    )
    wrong_folder = Folder.objects.create(
        project=other_project,
        parent=public_staff_root,
        name="工作证",
        code="WORK-CARD",
        created_by=admin,
    )
    document = Document.objects.create(
        project=archived_project,
        folder=wrong_folder,
        title="工作证扫描件",
        created_by=admin,
    )
    archive_project_folders(
        actor=admin,
        project=archived_project,
        archived_at=archived_project.archived_at,
    )
    archive_year = Folder.objects.get(code=f"PUBLIC-ARCHIVE-{archived_project.archived_at.year}")

    dry_run_repairs = repair_archived_document_folders(dry_run=True)
    document.refresh_from_db()

    assert len(dry_run_repairs) == 1
    assert document.folder == wrong_folder

    repairs = repair_archived_document_folders(dry_run=False)
    document.refresh_from_db()
    target_folder = document.folder

    assert len(repairs) == 1
    assert target_folder.project == archived_project
    assert target_folder.name == "工作证"
    assert target_folder.parent.name == "人员资质"
    assert target_folder.parent.parent.code == f"PROJECT-ARCHIVE-{archived_project.id}"
    assert document.id in Document.objects.filter(
        folder_id__in=descendant_folder_ids(str(archive_year.id))
    ).values_list("id", flat=True)


@pytest.mark.django_db
def test_repair_archived_document_folder_command_dry_run_does_not_change_data():
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(
        name="归档项目",
        code="P002",
        created_by=admin,
        archived_by=admin,
        archived_at=timezone.now(),
        status=Project.Status.ARCHIVED,
    )
    wrong_folder = Folder.objects.create(name="历史目录", created_by=admin)
    document = Document.objects.create(
        project=project,
        folder=wrong_folder,
        title="历史资料",
        created_by=admin,
    )

    call_command("repair_archived_document_folders")
    document.refresh_from_db()

    assert document.folder == wrong_folder
