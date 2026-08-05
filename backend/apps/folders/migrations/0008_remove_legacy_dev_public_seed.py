from pathlib import Path, PurePosixPath

from django.conf import settings
from django.db import migrations, transaction

LEGACY_ROOT_CODE = "DEV_PUBLIC"
LEGACY_ROOT_NAME = "开发公共资料"
LEGACY_CHILD_CODE = "QUALIFICATION"
LEGACY_CHILD_NAME = "公司资质"
LEGACY_DOCUMENT_TITLE = "营业执照示例"
LEGACY_DOCUMENT_FILENAME = "business-license-demo.pdf"
LEGACY_DOCUMENT_SIZE = 37
LEGACY_DOCUMENT_SHA256 = "8f1306a0fad835ae406b4dff4143cb24754146dbb1f730fe646fcebaaa6aae07"


def remove_legacy_dev_public_seed(apps, schema_editor):
    folder_model = apps.get_model("folders", "Folder")
    document_model = apps.get_model("documents", "Document")
    version_model = apps.get_model("documents", "DocumentVersion")
    storage_paths: list[str] = []

    roots = folder_model.objects.filter(
        project=None,
        parent=None,
        code=LEGACY_ROOT_CODE,
        name=LEGACY_ROOT_NAME,
    )
    for root in roots.iterator():
        children = list(folder_model.objects.filter(parent_id=root.pk).order_by("id"))
        if len(children) != 1:
            continue

        child = children[0]
        if child.name != LEGACY_CHILD_NAME or child.code != LEGACY_CHILD_CODE:
            continue
        if folder_model.objects.filter(parent_id=child.pk).exists():
            continue

        documents = list(
            document_model.objects.filter(folder_id__in=[root.pk, child.pk]).order_by("id")
        )
        if len(documents) != 1:
            continue

        document = documents[0]
        versions = list(version_model.objects.filter(document_id=document.pk).order_by("id"))
        if len(versions) != 1:
            continue

        version = versions[0]
        if (
            document.title != LEGACY_DOCUMENT_TITLE
            or document.current_version_id != version.pk
            or version.original_filename != LEGACY_DOCUMENT_FILENAME
            or version.file_size != LEGACY_DOCUMENT_SIZE
            or version.sha256 != LEGACY_DOCUMENT_SHA256
        ):
            continue

        storage_paths.append(version.storage_path)
        document.current_version_id = None
        document.save(update_fields=["current_version"])
        document.delete()
        child.delete()
        root.delete()

    if storage_paths:
        transaction.on_commit(lambda: _delete_legacy_files(storage_paths))


def _delete_legacy_files(storage_paths: list[str]) -> None:
    storage_root = Path(settings.FILE_STORAGE_ROOT).resolve()
    for storage_path in storage_paths:
        normalized_path = PurePosixPath(storage_path.replace("\\", "/"))
        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            continue
        candidate = storage_root.joinpath(*normalized_path.parts).resolve()
        try:
            candidate.relative_to(storage_root)
            candidate.unlink(missing_ok=True)
        except (OSError, ValueError):
            # Database cleanup is still valid if an obsolete file is already absent
            # or the deployment's storage volume is temporarily unavailable.
            continue


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0004_document_source_type"),
        ("folders", "0007_rename_completion_to_entry_preparation"),
    ]

    operations = [
        migrations.RunPython(remove_legacy_dev_public_seed, migrations.RunPython.noop),
    ]
