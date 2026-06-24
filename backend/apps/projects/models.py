from django.conf import settings
from django.db import models


class Project(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "进行中"
        ARCHIVED = "archived", "已归档"

    name = models.CharField("项目名称", max_length=120)
    code = models.CharField("项目编号", max_length=50, unique=True)
    description = models.TextField("描述", blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_projects",
        verbose_name="项目负责人",
    )
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_projects",
        verbose_name="创建人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    archived_at = models.DateTimeField("归档时间", null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="archived_projects",
        verbose_name="归档人",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status"], name="project_status_idx"),
            models.Index(fields=["manager"], name="project_manager_idx"),
            models.Index(fields=["created_at"], name="project_created_idx"),
        ]
        verbose_name = "项目"
        verbose_name_plural = "项目"

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class ProjectMember(models.Model):
    class Role(models.TextChoices):
        MANAGER = "manager", "负责人"
        OPERATOR = "operator", "资料整理员"
        VIEWER = "viewer", "查看者"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="members",
        verbose_name="项目",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
        verbose_name="用户",
    )
    role = models.CharField("项目角色", max_length=20, choices=Role.choices, default=Role.VIEWER)
    can_upload = models.BooleanField("可上传", default=False)
    can_download_restricted = models.BooleanField("可下载受限文件", default=False)
    can_manage_folder = models.BooleanField("可管理文件夹", default=False)
    can_delete = models.BooleanField("可删除", default=False)
    can_restore = models.BooleanField("可恢复", default=False)
    can_manage_permission = models.BooleanField("可管理授权", default=False)
    joined_at = models.DateTimeField("加入时间", auto_now_add=True)

    class Meta:
        ordering = ["project_id", "id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="unique_project_member"),
        ]
        indexes = [
            models.Index(fields=["project", "role"], name="member_project_role_idx"),
            models.Index(fields=["user"], name="member_user_idx"),
        ]
        verbose_name = "项目成员"
        verbose_name_plural = "项目成员"

    def __str__(self) -> str:
        return f"{self.project_id}:{self.user_id}:{self.role}"
