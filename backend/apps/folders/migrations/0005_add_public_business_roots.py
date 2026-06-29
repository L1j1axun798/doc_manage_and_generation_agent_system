from django.db import migrations

STANDARD_PUBLIC_ROOTS = [
    {
        "code": "PUBLIC-COMPLETION",
        "name": "竣工资料档案",
        "sort_order": 1,
        "aliases": ("竣工档案资料", "完工资料档案", "完工资料", "档案资料", "项目过程资料", "过程资料", "检测报告", "其他附件"),
    },
    {"code": "PUBLIC-COMPANY", "name": "公司资质", "sort_order": 2, "aliases": ()},
    {"code": "PUBLIC-TECH-SOLUTION", "name": "技术方案", "sort_order": 3, "aliases": ()},
    {"code": "PUBLIC-REPORT-TEMPLATE", "name": "报告模板", "sort_order": 4, "aliases": ()},
    {"code": "PUBLIC-TOOLS", "name": "工器具及年检资质", "sort_order": 5, "aliases": ("工具及年检资质", "工器具年检资质")},
    {
        "code": "PUBLIC-INSTRUMENT",
        "name": "仪器仪表设备年检资质",
        "sort_order": 6,
        "aliases": ("仪器设备年检资质",),
    },
    {"code": "PUBLIC-VEHICLE", "name": "车辆年检资质", "sort_order": 7, "aliases": ("车辆年检及资质",)},
    {"code": "PUBLIC-STAFF", "name": "人员资质", "sort_order": 8, "aliases": ()},
    {"code": "PUBLIC-STAFF-INSURANCE", "name": "人员保险单", "sort_order": 9, "aliases": ("人员报销单",)},
    {
        "code": "PUBLIC-PROTECTION",
        "name": "个人防护用品",
        "sort_order": 10,
        "aliases": ("劳动防护用品资料", "劳动防护用品"),
    },
]

ARCHIVE_ROOT = {
    "code": "PUBLIC-ARCHIVE",
    "name": "已归档文件",
    "sort_order": 99,
    "aliases": ("归档材料", "归档资料"),
}


def add_public_business_roots(apps, schema_editor):
    folder_model = apps.get_model("folders", "Folder")
    project_model = apps.get_model("projects", "Project")

    for definition in [*STANDARD_PUBLIC_ROOTS, ARCHIVE_ROOT]:
        root = upsert_public_root(folder_model, definition)
        deactivate_duplicate_alias_roots(folder_model, definition, root.pk)

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


class Migration(migrations.Migration):
    dependencies = [
        ("folders", "0004_remove_empty_archived_project_standard_roots"),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_public_business_roots, migrations.RunPython.noop),
    ]
