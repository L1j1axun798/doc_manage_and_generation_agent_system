from django.db import migrations, models


ENTRY_PREPARATION_ROOT_CODE = "PUBLIC-COMPLETION"
ENTRANCE_MATERIAL = "entrance_material"


def mark_existing_entry_materials(apps, schema_editor):
    document_model = apps.get_model("documents", "Document")
    folder_model = apps.get_model("folders", "Folder")

    folder_ids = list(
        folder_model.objects.filter(
            code=ENTRY_PREPARATION_ROOT_CODE,
            project_id__isnull=False,
        ).values_list("id", flat=True)
    )
    frontier = folder_ids.copy()
    while frontier:
        child_ids = list(
            folder_model.objects.filter(parent_id__in=frontier).values_list("id", flat=True)
        )
        frontier = [folder_id for folder_id in child_ids if folder_id not in folder_ids]
        folder_ids.extend(frontier)

    document_model.objects.filter(
        project_id__isnull=False,
        folder_id__in=folder_ids,
    ).update(source_type=ENTRANCE_MATERIAL)


class Migration(migrations.Migration):
    dependencies = [
        ("folders", "0007_rename_completion_to_entry_preparation"),
        ("documents", "0003_document_deleted_at_document_deleted_by_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("project_upload", "普通项目资料"),
                    ("entrance_material", "入场前置资料"),
                ],
                db_index=True,
                default="project_upload",
                max_length=32,
                verbose_name="资料来源类型",
            ),
        ),
        migrations.RunPython(mark_existing_entry_materials, migrations.RunPython.noop),
    ]
