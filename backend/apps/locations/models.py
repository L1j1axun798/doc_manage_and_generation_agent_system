from django.conf import settings
from django.db import models


class LocationReport(models.Model):
    class ReportStatus(models.TextChoices):
        SUCCESS = "success", "定位成功"
        LOCATE_FAILED = "locate_failed", "定位失败"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="location_reports",
        verbose_name="用户",
    )
    longitude = models.DecimalField("经度", max_digits=9, decimal_places=6, null=True, blank=True)
    latitude = models.DecimalField("纬度", max_digits=8, decimal_places=6, null=True, blank=True)
    accuracy = models.DecimalField(
        "定位精度",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    address = models.CharField("地址", max_length=255, blank=True)
    report_status = models.CharField(
        "上报结果",
        max_length=32,
        choices=ReportStatus.choices,
        default=ReportStatus.SUCCESS,
    )
    failure_reason = models.CharField("失败原因", max_length=255, blank=True)
    reported_at = models.DateTimeField("上报时间")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["-reported_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-reported_at"], name="location_user_reported_idx"),
            models.Index(fields=["report_status"], name="location_status_idx"),
        ]
        verbose_name = "位置记录"
        verbose_name_plural = "位置记录"

    def __str__(self) -> str:
        return f"{self.user} {self.report_status} {self.reported_at:%Y-%m-%d %H:%M:%S}"
