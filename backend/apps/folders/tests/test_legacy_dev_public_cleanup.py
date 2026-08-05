import importlib

import pytest
from django.apps import apps

from apps.documents.models import Document, DocumentVersion
from apps.folders.models import Folder

cleanup_migration = importlib.import_module(
    "apps.folders.migrations.0008_remove_legacy_dev_public_seed"
)


def create_legacy_seed(*, tmp_path):
    root = Folder.objects.create(
        name="开发公共资料",
        code="DEV_PUBLIC",
        is_system_root=True,
    )
    child = Folder.objects.create(
        parent=root,
        name="公司资质",
        code="QUALIFICATION",
    )
    document = Document.objects.create(
        folder=child,
        title="营业执照示例",
        description="公共目录示例文件。",
    )
    storage_path = "8f/13/legacy-demo.bin"
    physical_path = tmp_path / storage_path
    physical_path.parent.mkdir(parents=True)
    physical_path.write_bytes(b"x" * 37)
    version = DocumentVersion.objects.create(
        document=document,
        version_number=1,
        original_filename="business-license-demo.pdf",
        content_type="application/pdf",
        file_size=37,
        sha256=cleanup_migration.LEGACY_DOCUMENT_SHA256,
        storage_path=storage_path,
    )
    document.current_version = version
    document.save(update_fields=["current_version"])
    return root, child, document, physical_path


@pytest.mark.django_db
def test_cleanup_removes_exact_legacy_seed_and_physical_file(
    tmp_path, settings, django_capture_on_commit_callbacks
):
    settings.FILE_STORAGE_ROOT = tmp_path
    root, child, document, physical_path = create_legacy_seed(tmp_path=tmp_path)

    with django_capture_on_commit_callbacks(execute=True):
        cleanup_migration.remove_legacy_dev_public_seed(apps, None)

    assert not Folder.objects.filter(pk__in=[root.pk, child.pk]).exists()
    assert not Document.objects.filter(pk=document.pk).exists()
    assert not physical_path.exists()


@pytest.mark.django_db
def test_cleanup_preserves_legacy_root_when_it_contains_unexpected_data(
    tmp_path, settings, django_capture_on_commit_callbacks
):
    settings.FILE_STORAGE_ROOT = tmp_path
    root, child, document, physical_path = create_legacy_seed(tmp_path=tmp_path)
    document.title = "正式营业执照"
    document.save(update_fields=["title"])

    with django_capture_on_commit_callbacks(execute=True):
        cleanup_migration.remove_legacy_dev_public_seed(apps, None)

    assert Folder.objects.filter(pk__in=[root.pk, child.pk]).count() == 2
    assert Document.objects.filter(pk=document.pk).exists()
    assert physical_path.exists()
