from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Category(models.TextChoices):
        SYSTEM = "system", "系统"
        DOCUMENT = "document", "文档"
        ACCESS = "access", "授权"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="接收人",
    )
    title = models.CharField("标题", max_length=120)
    message = models.TextField("内容")
    category = models.CharField(
        "分类",
        max_length=30,
        choices=Category.choices,
        default=Category.SYSTEM,
    )
    resource_type = models.CharField("资源类型", max_length=80, blank=True)
    resource_id = models.CharField("资源 ID", max_length=80, blank=True)
    is_read = models.BooleanField("已读", default=False)
    read_at = models.DateTimeField("阅读时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["recipient", "is_read"], name="notif_recipient_read_idx"),
            models.Index(fields=["created_at"], name="notif_created_idx"),
        ]
        verbose_name = "通知"
        verbose_name_plural = "通知"

    def __str__(self) -> str:
        return f"{self.recipient_id}:{self.title}"
