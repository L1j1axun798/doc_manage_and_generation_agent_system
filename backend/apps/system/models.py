from django.conf import settings
from django.db import models


class SystemBackupRun(models.Model):
    class Trigger(models.TextChoices):
        SCHEDULED = "scheduled", "计划任务"
        MANUAL = "manual", "手动"

    class Status(models.TextChoices):
        RUNNING = "running", "执行中"
        SUCCESS = "success", "成功"
        FAILURE = "failure", "失败"

    trigger = models.CharField("触发方式", max_length=20, choices=Trigger.choices)
    status = models.CharField("状态", max_length=20, choices=Status.choices)
    started_at = models.DateTimeField("开始时间")
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    local_path = models.CharField("服务器本机备份路径", max_length=1000, blank=True)
    offsite_path = models.CharField("可选离机副本路径", max_length=1000, blank=True)
    sha256 = models.CharField("SHA-256", max_length=64, blank=True)
    size_bytes = models.PositiveBigIntegerField("备份大小", default=0)
    error_message = models.TextField("失败原因", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="system_backup_runs",
        verbose_name="创建人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [
            models.Index(fields=["status", "started_at"], name="system_backup_status_idx"),
            models.Index(fields=["started_at"], name="system_backup_started_idx"),
        ]
        verbose_name = "系统备份记录"
        verbose_name_plural = "系统备份记录"

    def __str__(self) -> str:
        return f"{self.started_at:%Y-%m-%d %H:%M:%S} {self.status}"
