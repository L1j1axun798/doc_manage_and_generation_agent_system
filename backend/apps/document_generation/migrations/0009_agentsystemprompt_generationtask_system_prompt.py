import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("document_generation", "0008_generationtask_conversation_context"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentSystemPrompt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_filename", models.CharField(max_length=255, verbose_name="原始文件名")),
                ("version", models.CharField(max_length=80, verbose_name="版本")),
                ("content", models.TextField(verbose_name="System Prompt正文")),
                ("content_sha256", models.CharField(max_length=64, verbose_name="正文SHA-256")),
                ("is_active", models.BooleanField(default=True, verbose_name="当前启用")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="上传时间")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uploaded_agent_system_prompts", to=settings.AUTH_USER_MODEL, verbose_name="上传人")),
            ],
            options={
                "verbose_name": "Agent System Prompt",
                "verbose_name_plural": "Agent System Prompts",
                "ordering": ["-created_at", "-id"],
                "indexes": [models.Index(fields=["is_active", "-created_at"], name="docgen_sys_prompt_idx")],
            },
        ),
        migrations.AddField(
            model_name="generationtask",
            name="system_prompt",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="generation_tasks", to="document_generation.agentsystemprompt", verbose_name="System Prompt版本"),
        ),
        migrations.AddField(
            model_name="generationtask",
            name="system_prompt_sha256",
            field=models.CharField(blank=True, max_length=64, verbose_name="System Prompt SHA-256"),
        ),
        migrations.AddField(
            model_name="generationtask",
            name="system_prompt_snapshot",
            field=models.TextField(blank=True, verbose_name="System Prompt快照"),
        ),
    ]
