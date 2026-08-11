from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.documents.models import Document, DocumentVersion
from apps.folders.models import Folder
from common.storage import LocalDocumentStorage

User = get_user_model()


def make_legacy_version(*, tmp_path, settings) -> DocumentVersion:
    settings.FILE_STORAGE_ROOT = tmp_path
    user = User.objects.create_user(
        username="admin",
        password="Password123!",
        real_name="admin",
        role=User.Role.SYSTEM_ADMIN,
    )
    folder = Folder.objects.create(name="资料", created_by=user)
    document = Document.objects.create(folder=folder, title="报告", created_by=user)
    storage = LocalDocumentStorage()
    stored = storage.save_uploaded_file(SimpleUploadedFile("report.pdf", b"content"))
    version = DocumentVersion.objects.create(
        document=document,
        version_number=1,
        original_filename="report.pdf",
        content_type="application/pdf",
        file_size=stored.size,
        sha256=stored.sha256,
        storage_path=stored.relative_path.replace("/", "\\"),
        uploaded_by=user,
    )
    document.current_version = version
    document.save(update_fields=["current_version"])
    return version


@pytest.mark.django_db
def test_storage_path_repair_dry_run_then_apply(tmp_path, settings):
    version = make_legacy_version(tmp_path=tmp_path, settings=settings)
    output = StringIO()

    call_command("repair_document_storage_paths", stdout=output)
    version.refresh_from_db()
    assert "\\" in version.storage_path
    assert "待修复 1 条" in output.getvalue()

    output = StringIO()
    call_command("repair_document_storage_paths", apply=True, stdout=output)
    version.refresh_from_db()
    assert "\\" not in version.storage_path
    assert LocalDocumentStorage().exists(version.storage_path)
    assert "已修复 1 条" in output.getvalue()


@pytest.mark.django_db
def test_storage_path_repair_refuses_hash_mismatch(tmp_path, settings):
    version = make_legacy_version(tmp_path=tmp_path, settings=settings)
    version.sha256 = "0" * 64
    version.save(update_fields=["sha256"])

    with pytest.raises(CommandError, match="SHA-256 不一致"):
        call_command("repair_document_storage_paths", apply=True)

    version.refresh_from_db()
    assert "\\" in version.storage_path
