from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Folder(models.Model):
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="folders",
        verbose_name="所属项目",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        verbose_name="父文件夹",
    )
    name = models.CharField("文件夹名称", max_length=120)
    code = models.CharField("文件夹编码", max_length=50, blank=True)
    sort_order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    is_system_root = models.BooleanField("系统根分类", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_folders",
        verbose_name="创建人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["project", "parent"], name="folder_project_parent_idx"),
            models.Index(fields=["is_active"], name="folder_active_idx"),
            models.Index(fields=["code"], name="folder_code_idx"),
        ]
        verbose_name = "文件夹"
        verbose_name_plural = "文件夹"

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        if self.project_id is None and self.parent_id is None and not self.is_system_root:
            raise ValidationError("公共文件夹必须归属于某个系统根分类")
        if self.is_system_root:
            if self.project_id is not None or self.parent_id is not None:
                raise ValidationError("系统根分类必须位于公共根目录")
            if not self.is_active:
                raise ValidationError("系统根分类不能停用")


class PersonnelProfile(models.Model):
    class Gender(models.TextChoices):
        UNKNOWN = "unknown", "未填写"
        MALE = "male", "男"
        FEMALE = "female", "女"

    folder = models.OneToOneField(
        Folder,
        on_delete=models.CASCADE,
        related_name="personnel_profile",
        verbose_name="人员目录",
    )
    gender = models.CharField(
        "性别",
        max_length=16,
        choices=Gender.choices,
        default=Gender.UNKNOWN,
    )
    id_card_number = models.CharField("身份证号", max_length=32, blank=True)
    phone = models.CharField("手机号", max_length=30, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_personnel_profiles",
        verbose_name="最后修改人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["folder__sort_order", "folder_id"]
        indexes = [
            models.Index(fields=["gender"], name="personnel_gender_idx"),
            models.Index(fields=["updated_at"], name="personnel_updated_idx"),
        ]
        verbose_name = "人员信息"
        verbose_name_plural = "人员信息"

    def __str__(self) -> str:
        return self.folder.name
