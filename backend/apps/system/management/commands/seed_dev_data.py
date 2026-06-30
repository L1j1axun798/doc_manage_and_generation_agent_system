from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.access.models import DocumentGrant
from apps.documents.models import Document
from apps.documents.services import create_document
from apps.folders.defaults import STANDARD_PUBLIC_ROOTS
from apps.folders.models import Folder
from apps.notifications.models import Notification
from apps.notifications.services import create_notification
from apps.projects.models import Project, ProjectMember
from apps.projects.services import ensure_project_standard_folders, manager_member_defaults

User = get_user_model()

DEV_PASSWORD = "Password123!"
PROJECT_CODE = "DEMO-FRONTEND"


class Command(BaseCommand):
    help = "Create deterministic development data for frontend integration."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow running outside DEBUG. Use only on disposable environments.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG and not options["force"]:
            raise CommandError("seed_dev_data 仅允许在 DEBUG 环境运行；确需执行请显式传入 --force")

        with transaction.atomic():
            admin = self._upsert_user(
                username="admin",
                real_name="系统管理员",
                role=User.Role.SYSTEM_ADMIN,
                employee_no="DEV-ADMIN",
                is_superuser=True,
                is_staff=True,
            )
            manager = self._upsert_user(
                username="manager",
                real_name="项目负责人",
                role=User.Role.PROJECT_MANAGER,
                employee_no="DEV-MANAGER",
            )
            operator = self._upsert_user(
                username="operator",
                real_name="资料整理员",
                role=User.Role.DATA_OPERATOR,
                employee_no="DEV-OPERATOR",
            )
            viewer = self._upsert_user(
                username="viewer",
                real_name="只读查看者",
                role=User.Role.DATA_OPERATOR,
                employee_no="DEV-VIEWER",
            )

            project, _ = Project.objects.update_or_create(
                code=PROJECT_CODE,
                defaults={
                    "name": "前端联调示例项目",
                    "description": "用于前端开发联调的固定示例数据，可重复执行生成。",
                    "manager": manager,
                    "created_by": admin,
                    "status": Project.Status.ACTIVE,
                    "archived_at": None,
                    "archived_by": None,
                },
            )
            self._upsert_members(project=project, manager=manager, operator=operator, viewer=viewer)
            ensure_project_standard_folders(actor=admin, project=project)

            company_root = next(
                definition
                for definition in STANDARD_PUBLIC_ROOTS
                if definition.code == "PUBLIC-COMPANY"
            )
            completion_root = next(
                definition
                for definition in STANDARD_PUBLIC_ROOTS
                if definition.code == "PUBLIC-COMPLETION"
            )
            public_root, _ = Folder.objects.update_or_create(
                project=None,
                parent=None,
                code=company_root.code,
                defaults={
                    "name": company_root.name,
                    "is_system_root": True,
                    "sort_order": company_root.sort_order,
                    "created_by": admin,
                },
            )
            public_folder, _ = Folder.objects.update_or_create(
                project=None,
                parent=public_root,
                code="PUBLIC-COMPANY-DEMO",
                defaults={
                    "name": "示例公司",
                    "is_system_root": False,
                    "is_active": True,
                    "sort_order": 1,
                    "created_by": admin,
                },
            )
            report_folder, _ = Folder.objects.update_or_create(
                project=project,
                parent=None,
                code=completion_root.code,
                defaults={
                    "name": completion_root.name,
                    "sort_order": completion_root.sort_order,
                    "created_by": admin,
                    "is_active": True,
                },
            )

            public_document = self._ensure_document(
                actor=admin,
                folder=public_folder,
                title="营业执照示例",
                filename="business-license-demo.pdf",
                content=b"%PDF-1.4\nwind-doc-system public demo\n",
                access_level=Document.AccessLevel.INTERNAL,
                description="公共目录示例文件。",
            )
            internal_document = self._ensure_document(
                actor=operator,
                folder=report_folder,
                title="机组叶片检测报告",
                filename="blade-inspection-report.pdf",
                content=b"%PDF-1.4\nwind turbine blade inspection report demo\n",
                access_level=Document.AccessLevel.INTERNAL,
                description="内部项目成员可见的示例检测报告。",
            )
            restricted_document = self._ensure_document(
                actor=manager,
                folder=report_folder,
                title="受限缺陷复核记录",
                filename="restricted-defect-review.pdf",
                content=b"%PDF-1.4\nrestricted defect review demo\n",
                access_level=Document.AccessLevel.RESTRICTED,
                description="用于验证 DocumentGrant 和受限文件权限。",
            )

            DocumentGrant.objects.update_or_create(
                document=restricted_document,
                user=viewer,
                revoked_at=None,
                defaults={
                    "can_view": True,
                    "can_download": True,
                    "can_update": False,
                    "can_delete": False,
                    "can_restore": False,
                    "can_manage": False,
                    "expires_at": timezone.now() + timedelta(days=30),
                    "created_by": manager,
                },
            )
            self._ensure_notification(
                recipient=operator,
                title="示例项目已准备",
                message="前端联调示例项目、文件夹和文档已初始化。",
                resource_type="Project",
                resource_id=str(project.pk),
            )

        self.stdout.write(self.style.SUCCESS("开发种子数据已准备完成，可重复执行。"))
        self.stdout.write("登录账号：admin / manager / operator / viewer")
        self.stdout.write(f"统一密码：{DEV_PASSWORD}")
        self.stdout.write(f"项目编号：{PROJECT_CODE}")
        self.stdout.write(
            "示例文档："
            f"public={public_document.pk}, internal={internal_document.pk}, "
            f"restricted={restricted_document.pk}"
        )

    def _upsert_user(
        self,
        *,
        username: str,
        real_name: str,
        role: str,
        employee_no: str,
        is_superuser: bool = False,
        is_staff: bool = False,
    ) -> Any:
        user, _ = User.objects.update_or_create(
            username=username,
            defaults={
                "real_name": real_name,
                "employee_no": employee_no,
                "role": role,
                "email": f"{username}@example.local",
                "is_active": True,
                "is_superuser": is_superuser,
                "is_staff": is_staff or is_superuser,
                "must_change_password": False,
            },
        )
        user.set_password(DEV_PASSWORD)
        user.save(update_fields=["password", "must_change_password"])
        return user

    def _upsert_members(
        self,
        *,
        project: Project,
        manager: Any,
        operator: Any,
        viewer: Any,
    ) -> None:
        ProjectMember.objects.update_or_create(
            project=project,
            user=manager,
            defaults=manager_member_defaults(),
        )
        ProjectMember.objects.update_or_create(
            project=project,
            user=operator,
            defaults={
                "role": ProjectMember.Role.OPERATOR,
                "can_upload": True,
                "can_download_restricted": False,
                "can_manage_folder": True,
                "can_delete": True,
                "can_restore": True,
                "can_manage_permission": False,
            },
        )
        ProjectMember.objects.update_or_create(
            project=project,
            user=viewer,
            defaults={
                "role": ProjectMember.Role.VIEWER,
                "can_upload": False,
                "can_download_restricted": False,
                "can_manage_folder": False,
                "can_delete": False,
                "can_restore": False,
                "can_manage_permission": False,
            },
        )

    def _ensure_document(
        self,
        *,
        actor: Any,
        folder: Folder,
        title: str,
        filename: str,
        content: bytes,
        access_level: str,
        description: str,
    ) -> Document:
        document = Document.objects.filter(
            folder=folder,
            title=title,
            deleted_at__isnull=True,
        ).first()
        if document is not None:
            return document
        uploaded_file = SimpleUploadedFile(filename, content, content_type="application/pdf")
        return create_document(
            actor=actor,
            folder=folder,
            uploaded_file=uploaded_file,
            title=title,
            description=description,
            access_level=access_level,
        )

    def _ensure_notification(
        self,
        *,
        recipient: Any,
        title: str,
        message: str,
        resource_type: str,
        resource_id: str,
    ) -> None:
        if Notification.objects.filter(
            recipient=recipient,
            title=title,
            resource_type=resource_type,
            resource_id=resource_id,
        ).exists():
            return
        create_notification(
            recipient=recipient,
            title=title,
            message=message,
            category=Notification.Category.SYSTEM,
            resource_type=resource_type,
            resource_id=resource_id,
        )
