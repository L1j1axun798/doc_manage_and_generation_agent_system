from django.conf import settings
from django.db import models
from django.utils import timezone


class DocumentGrant(models.Model):
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="grants",
        verbose_name="文档",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_grants",
        verbose_name="被授权用户",
    )
    can_view = models.BooleanField("可查看", default=False)
    can_download = models.BooleanField("可下载", default=False)
    can_update = models.BooleanField("可更新", default=False)
    can_delete = models.BooleanField("可删除", default=False)
    can_restore = models.BooleanField("可恢复", default=False)
    can_manage = models.BooleanField("可管理授权", default=False)
    expires_at = models.DateTimeField("过期时间", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_document_grants",
        verbose_name="授权人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    revoked_at = models.DateTimeField("撤销时间", null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_document_grants",
        verbose_name="撤销人",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["document", "user"], name="grant_document_user_idx"),
            models.Index(fields=["user", "revoked_at"], name="grant_user_revoked_idx"),
            models.Index(fields=["expires_at"], name="grant_expires_idx"),
        ]
        verbose_name = "文档授权"
        verbose_name_plural = "文档授权"

    def __str__(self) -> str:
        return f"{self.document_id}:{self.user_id}"

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and not self.is_expired


class TemporaryAccessGrant(models.Model):
    document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.CASCADE,
        related_name="temporary_access_grants",
        verbose_name="文档版本",
    )
    token_hash = models.CharField("Token 哈希", max_length=64, unique=True)
    max_downloads = models.PositiveIntegerField("最大下载次数", default=1)
    used_count = models.PositiveIntegerField("已使用次数", default=0)
    expires_at = models.DateTimeField("过期时间")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_temporary_access_grants",
        verbose_name="创建人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    revoked_at = models.DateTimeField("撤销时间", null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_temporary_access_grants",
        verbose_name="撤销人",
    )
    last_used_at = models.DateTimeField("最后使用时间", null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["document_version", "revoked_at"],
                name="temp_document_revoked_idx",
            ),
            models.Index(fields=["expires_at"], name="temp_expires_idx"),
            models.Index(fields=["created_by"], name="temp_created_by_idx"),
        ]
        verbose_name = "临时访问授权"
        verbose_name_plural = "临时访问授权"

    def __str__(self) -> str:
        return f"{self.document_version_id}:{self.pk}"

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    @property
    def remaining_downloads(self) -> int:
        return max(self.max_downloads - self.used_count, 0)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and not self.is_expired and self.remaining_downloads > 0
