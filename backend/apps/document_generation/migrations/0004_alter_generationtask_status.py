from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("document_generation", "0003_generationtraceevent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="generationtask",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "草稿"),
                    ("extracting", "提取事实"),
                    ("needs_confirmation", "待确认事实"),
                    ("ready", "可生成"),
                    ("queued", "已排队"),
                    ("generating", "生成中"),
                    ("review_required", "待审核"),
                    ("pending_approval", "待批准"),
                    ("approved", "已批准"),
                    ("exported", "已导出"),
                    ("failed", "失败"),
                ],
                default="draft",
                max_length=30,
                verbose_name="状态",
            ),
        ),
    ]
