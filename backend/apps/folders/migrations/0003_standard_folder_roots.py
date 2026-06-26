import re

from django.db import migrations

STANDARD_PUBLIC_ROOTS = [
    {
        "code": "PUBLIC-COMPLETION",
        "name": "竣工档案资料",
        "sort_order": 1,
        "aliases": ("完工资料档案", "完工资料", "档案资料", "项目过程资料", "过程资料", "检测报告", "其他附件"),
    },
    {"code": "PUBLIC-COMPANY", "name": "公司资质", "sort_order": 2, "aliases": ()},
    {"code": "PUBLIC-STAFF", "name": "人员资质", "sort_order": 3, "aliases": ()},
    {"code": "PUBLIC-TOOLS", "name": "工具及年检资质", "sort_order": 4, "aliases": ("工器具年检资质",)},
    {
        "code": "PUBLIC-INSTRUMENT",
        "name": "仪器仪表设备年检资质",
        "sort_order": 5,
        "aliases": ("仪器设备年检资质",),
    },
    {"code": "PUBLIC-VEHICLE", "name": "车辆年检资质", "sort_order": 6, "aliases": ("车辆年检及资质",)},
    {
        "code": "PUBLIC-PROTECTION",
        "name": "个人防护用品",
        "sort_order": 7,
        "aliases": ("劳动防护用品资料", "劳动防护用品"),
    },
]

ARCHIVE_ROOT = {
    "code": "PUBLIC-ARCHIVE",
    "name": "归档资料",
    "sort_order": 99,
    "aliases": (),
}


def normalize_standard_folders(apps, schema_editor):
    folder_model = apps.get_model("folders", "Folder")
    project_model = apps.get_model("projects", "Project")

    for definition in [*STANDARD_PUBLIC_ROOTS, ARCHIVE_ROOT]:
        root = upsert_public_root(folder_model, definition)
        deactivate_duplicate_alias_roots(folder_model, definition, root.pk)

    archive_root = upsert_public_root(folder_model, ARCHIVE_ROOT)
    move_legacy_archive_year_roots(folder_model, archive_root)

    for project in project_model.objects.filter(status="active"):
        for definition in STANDARD_PUBLIC_ROOTS:
            folder_model.objects.update_or_create(
                project=project,
                parent=None,
                code=definition["code"],
                defaults={
                    "name": definition["name"],
                    "sort_order": definition["sort_order"],
                    "is_active": True,
                    "is_system_root": False,
                },
            )


def upsert_public_root(folder_model, definition):
    names = (definition["name"], *definition["aliases"])
    folder = (
        folder_model.objects.filter(project=None, parent=None, name__in=names)
        .order_by("id")
        .first()
    )
    if folder is None:
        return folder_model.objects.create(
            project=None,
            parent=None,
            name=definition["name"],
            code=definition["code"],
            sort_order=definition["sort_order"],
            is_active=True,
            is_system_root=True,
        )

    folder.name = definition["name"]
    folder.code = definition["code"]
    folder.sort_order = definition["sort_order"]
    folder.is_active = True
    folder.is_system_root = True
    folder.save(
        update_fields=[
            "name",
            "code",
            "sort_order",
            "is_active",
            "is_system_root",
            "updated_at",
        ]
    )
    return folder


def deactivate_duplicate_alias_roots(folder_model, definition, canonical_id):
    if not definition["aliases"]:
        return
    folder_model.objects.filter(
        project=None,
        parent=None,
        name__in=definition["aliases"],
    ).exclude(pk=canonical_id).update(is_active=False)


def move_legacy_archive_year_roots(folder_model, archive_root):
    for folder in folder_model.objects.filter(project=None, parent=None):
        match = re.fullmatch(r"(\d{4})年归档资料", folder.name)
        if match is None:
            continue
        year = match.group(1)
        folder.parent = archive_root
        folder.code = f"{ARCHIVE_ROOT['code']}-{year}"
        folder.sort_order = int(year)
        folder.is_system_root = False
        folder.is_active = True
        folder.save(
            update_fields=[
                "parent",
                "code",
                "sort_order",
                "is_system_root",
                "is_active",
                "updated_at",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("folders", "0002_folder_is_system_root"),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(normalize_standard_folders, migrations.RunPython.noop),
    ]
