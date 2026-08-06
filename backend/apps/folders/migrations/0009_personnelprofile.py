import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("folders", "0008_remove_legacy_dev_public_seed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonnelProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "gender",
                    models.CharField(
                        choices=[("unknown", "未填写"), ("male", "男"), ("female", "女")],
                        default="unknown",
                        max_length=16,
                        verbose_name="性别",
                    ),
                ),
                ("id_card_number", models.CharField(blank=True, max_length=32, verbose_name="身份证号")),
                ("phone", models.CharField(blank=True, max_length=30, verbose_name="手机号")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "folder",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="personnel_profile",
                        to="folders.folder",
                        verbose_name="人员目录",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_personnel_profiles",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="最后修改人",
                    ),
                ),
            ],
            options={
                "verbose_name": "人员信息",
                "verbose_name_plural": "人员信息",
                "ordering": ["folder__sort_order", "folder_id"],
            },
        ),
        migrations.AddIndex(
            model_name="personnelprofile",
            index=models.Index(fields=["gender"], name="personnel_gender_idx"),
        ),
        migrations.AddIndex(
            model_name="personnelprofile",
            index=models.Index(fields=["updated_at"], name="personnel_updated_idx"),
        ),
    ]
