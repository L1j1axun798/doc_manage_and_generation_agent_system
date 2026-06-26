from typing import Any

from django.core.management.base import BaseCommand

from apps.folders.defaults import ARCHIVE_ROOT, STANDARD_PUBLIC_ROOTS
from apps.folders.models import Folder


class Command(BaseCommand):
    help = "初始化公共资料基础目录"

    def handle(self, *args: Any, **options: Any) -> None:
        for definition in [*STANDARD_PUBLIC_ROOTS, ARCHIVE_ROOT]:
            folder = (
                Folder.objects.filter(
                    project=None,
                    parent=None,
                    name__in=definition.names,
                )
                .order_by("id")
                .first()
            )
            if folder is None:
                folder = Folder.objects.create(
                    project=None,
                    parent=None,
                    name=definition.name,
                    code=definition.code,
                    sort_order=definition.sort_order,
                    is_system_root=True,
                )
                continue

            folder.name = definition.name
            folder.code = definition.code
            folder.sort_order = definition.sort_order
            folder.is_system_root = True
            folder.is_active = True
            folder.save(
                update_fields=[
                    "name",
                    "code",
                    "sort_order",
                    "is_system_root",
                    "is_active",
                    "updated_at",
                ]
            )

            Folder.objects.filter(
                project=None,
                parent=None,
                name__in=definition.aliases,
            ).exclude(pk=folder.pk).update(is_active=False)
        self.stdout.write(self.style.SUCCESS("公共资料基础目录已初始化"))
