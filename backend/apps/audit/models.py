from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Result(models.TextChoices):
        SUCCESS = "success", "成功"
        FAILURE = "failure", "失败"
        DENIED = "denied", "拒绝"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        verbose_name="操作者",
    )
    action = models.CharField("动作", max_length=100)
    resource_type = models.CharField("资源类型", max_length=100, blank=True)
    resource_id = models.CharField("资源 ID", max_length=100, blank=True)
    result = models.CharField("结果", max_length=20, choices=Result.choices)
    ip_address = models.GenericIPAddressField("IP 地址", null=True, blank=True)
    user_agent = models.TextField("User-Agent", blank=True)
    request_id = models.CharField("请求 ID", max_length=64, blank=True)
    before_data = models.JSONField("变更前", null=True, blank=True)
    after_data = models.JSONField("变更后", null=True, blank=True)
    error_message = models.TextField("错误原因", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["created_at"], name="audit_created_at_idx"),
            models.Index(fields=["action"], name="audit_action_idx"),
            models.Index(fields=["resource_type", "resource_id"], name="audit_resource_idx"),
            models.Index(fields=["user"], name="audit_user_idx"),
        ]
        verbose_name = "审计日志"
        verbose_name_plural = "审计日志"

    def __str__(self) -> str:
        return f"{self.action}:{self.result}"
