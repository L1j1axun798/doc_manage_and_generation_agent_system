from django.db import migrations

STANDARD_PUBLIC_ROOT_CODES = [
    "PUBLIC-COMPLETION",
    "PUBLIC-COMPANY",
    "PUBLIC-STAFF",
    "PUBLIC-TOOLS",
    "PUBLIC-INSTRUMENT",
    "PUBLIC-VEHICLE",
    "PUBLIC-PROTECTION",
]


def remove_empty_archived_project_standard_roots(apps, schema_editor):
    folder_model = apps.get_model("folders", "Folder")
    document_model = apps.get_model("documents", "Document")

    folders = folder_model.objects.filter(
        project__status="archived",
        parent=None,
        code__in=STANDARD_PUBLIC_ROOT_CODES,
    ).order_by("-id")
    for folder in folders:
        if folder_model.objects.filter(parent=folder).exists():
            continue
        if document_model.objects.filter(folder=folder).exists():
            continue
        folder.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0003_document_deleted_at_document_deleted_by_and_more"),
        ("folders", "0003_standard_folder_roots"),
    ]

    operations = [
        migrations.RunPython(
            remove_empty_archived_project_standard_roots,
            migrations.RunPython.noop,
        ),
    ]
