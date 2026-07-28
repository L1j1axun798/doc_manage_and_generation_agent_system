from django.db import migrations


ENTRY_PREPARATION_ROOT_CODE = "PUBLIC-COMPLETION"
ENTRY_PREPARATION_ROOT_NAME = "入场前置资料"


def rename_entry_preparation_roots(apps, schema_editor):
    folder_model = apps.get_model("folders", "Folder")
    folder_model.objects.filter(code=ENTRY_PREPARATION_ROOT_CODE).update(
        name=ENTRY_PREPARATION_ROOT_NAME
    )


class Migration(migrations.Migration):
    dependencies = [
        ("folders", "0006_normalize_archive_root_name"),
    ]

    operations = [
        migrations.RunPython(rename_entry_preparation_roots, migrations.RunPython.noop),
    ]
