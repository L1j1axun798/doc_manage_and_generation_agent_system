from typing import Any

from django.core.management.base import BaseCommand

from apps.folders.models import Folder


class Command(BaseCommand):
    help = "初始化公共资料基础目录"

    DEFAULT_FOLDERS = [
        "完工资料档案",
        "公司资质",
        "人员资质",
        "工器具年检资质",
        "劳动防护用品资料",
        "仪器设备年检资质",
        "车辆年检及资质",
    ]

    def handle(self, *args: Any, **options: Any) -> None:
        for index, name in enumerate(self.DEFAULT_FOLDERS, start=1):
            Folder.objects.get_or_create(
                project=None,
                parent=None,
                name=name,
                defaults={
                    "code": f"PUBLIC-{index:02d}",
                    "sort_order": index,
                    "is_system_root": True,
                },
            )
            Folder.objects.filter(project=None, parent=None, name=name).update(is_system_root=True)
        self.stdout.write(self.style.SUCCESS("公共资料基础目录已初始化"))
