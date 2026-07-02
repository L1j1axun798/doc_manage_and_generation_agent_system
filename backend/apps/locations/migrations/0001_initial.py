# Generated manually for the personnel location V1 feature.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LocationReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "longitude",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                        verbose_name="经度",
                    ),
                ),
                (
                    "latitude",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=8,
                        null=True,
                        verbose_name="纬度",
                    ),
                ),
                (
                    "accuracy",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=8,
                        null=True,
                        verbose_name="定位精度",
                    ),
                ),
                ("address", models.CharField(blank=True, max_length=255, verbose_name="地址")),
                (
                    "report_status",
                    models.CharField(
                        choices=[("success", "定位成功"), ("locate_failed", "定位失败")],
                        default="success",
                        max_length=32,
                        verbose_name="上报结果",
                    ),
                ),
                ("failure_reason", models.CharField(blank=True, max_length=255, verbose_name="失败原因")),
                ("reported_at", models.DateTimeField(verbose_name="上报时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="location_reports",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "位置记录",
                "verbose_name_plural": "位置记录",
                "ordering": ["-reported_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="locationreport",
            index=models.Index(fields=["user", "-reported_at"], name="location_user_reported_idx"),
        ),
        migrations.AddIndex(
            model_name="locationreport",
            index=models.Index(fields=["report_status"], name="location_status_idx"),
        ),
    ]
