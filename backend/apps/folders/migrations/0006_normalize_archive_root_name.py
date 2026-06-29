from django.db import migrations
from django.db.models import Q

ARCHIVE_ROOT = {
    "code": "PUBLIC-ARCHIVE",
    "name": "已归档文件",
    "sort_order": 99,
    "aliases": ("归档材料", "归档资料"),
}


def normalize_archive_root_name(apps, schema_editor):
    folder_model = apps.get_model("folders", "Folder")
    document_model = apps.get_model("documents", "Document")
    archive_names = (ARCHIVE_ROOT["name"], *ARCHIVE_ROOT["aliases"])

    archive_root = (
        folder_model.objects.filter(project=None, parent=None)
        .filter(Q(code=ARCHIVE_ROOT["code"]) | Q(name__in=archive_names))
        .order_by("id")
        .first()
    )
    if archive_root is None:
        archive_root = folder_model.objects.create(
            project=None,
            parent=None,
            name=ARCHIVE_ROOT["name"],
            code=ARCHIVE_ROOT["code"],
            sort_order=ARCHIVE_ROOT["sort_order"],
            is_active=True,
            is_system_root=True,
        )
    else:
        archive_root.name = ARCHIVE_ROOT["name"]
        archive_root.code = ARCHIVE_ROOT["code"]
        archive_root.sort_order = ARCHIVE_ROOT["sort_order"]
        archive_root.is_active = True
        archive_root.is_system_root = True
        archive_root.save(
            update_fields=[
                "name",
                "code",
                "sort_order",
                "is_active",
                "is_system_root",
                "updated_at",
            ]
        )

    duplicates = (
        folder_model.objects.filter(project=None, parent=None)
        .filter(Q(code=ARCHIVE_ROOT["code"]) | Q(name__in=archive_names))
        .exclude(pk=archive_root.pk)
    )
    for duplicate in duplicates:
        folder_model.objects.filter(parent=duplicate).update(parent=archive_root)
        document_model.objects.filter(folder=duplicate).update(folder=archive_root)
        duplicate.is_active = False
        duplicate.is_system_root = False
        duplicate.code = ""
        duplicate.save(update_fields=["is_active", "is_system_root", "code", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0003_document_deleted_at_document_deleted_by_and_more"),
        ("folders", "0005_add_public_business_roots"),
    ]

    operations = [
        migrations.RunPython(normalize_archive_root_name, migrations.RunPython.noop),
    ]
