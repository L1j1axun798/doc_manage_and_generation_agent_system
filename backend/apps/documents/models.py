from django.conf import settings
from django.db import models


class Document(models.Model):
    class AccessLevel(models.TextChoices):
        INTERNAL = "internal", "内部"
        RESTRICTED = "restricted", "受限"

    class SourceType(models.TextChoices):
        PROJECT_UPLOAD = "project_upload", "普通项目资料"
        ENTRANCE_MATERIAL = "entrance_material", "入场前置资料"

    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="所属项目",
    )
    folder = models.ForeignKey(
        "folders.Folder",
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name="所属文件夹",
    )
    title = models.CharField("文档标题", max_length=255)
    description = models.TextField("描述", blank=True)
    access_level = models.CharField(
        "访问级别",
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.INTERNAL,
    )
    source_type = models.CharField(
        "资料来源类型",
        max_length=32,
        choices=SourceType.choices,
        default=SourceType.PROJECT_UPLOAD,
        db_index=True,
    )
    current_version = models.ForeignKey(
        "documents.DocumentVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="current_for_documents",
        verbose_name="当前版本",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_documents",
        verbose_name="创建人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    lock_version = models.PositiveIntegerField("乐观锁版本", default=1)
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deleted_documents",
        verbose_name="删除人",
    )

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["project", "folder"], name="document_project_folder_idx"),
            models.Index(fields=["access_level"], name="document_access_level_idx"),
            models.Index(fields=["deleted_at"], name="document_deleted_at_idx"),
            models.Index(fields=["created_at"], name="document_created_idx"),
        ]
        verbose_name = "文档"
        verbose_name_plural = "文档"

    def __str__(self) -> str:
        return self.title

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class DocumentVersion(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="文档",
    )
    version_number = models.PositiveIntegerField("版本号")
    original_filename = models.CharField("原始文件名", max_length=255)
    content_type = models.CharField("内容类型", max_length=120, blank=True)
    file_size = models.PositiveBigIntegerField("文件大小")
    sha256 = models.CharField("SHA-256", max_length=64)
    storage_path = models.CharField("存储路径", max_length=500, unique=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_document_versions",
        verbose_name="上传人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["document_id", "-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version_number"],
                name="unique_document_version_number",
            ),
        ]
        indexes = [
            models.Index(fields=["document", "version_number"], name="docver_document_number_idx"),
            models.Index(fields=["sha256"], name="docver_sha256_idx"),
            models.Index(fields=["created_at"], name="docver_created_idx"),
        ]
        verbose_name = "文档版本"
        verbose_name_plural = "文档版本"

    def __str__(self) -> str:
        return f"{self.document_id} v{self.version_number}"
