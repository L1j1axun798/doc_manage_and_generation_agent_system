from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("document_generation", "0002_generationtask_operation"),
    ]

    operations = [
        migrations.CreateModel(
            name="GenerationTraceEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sequence", models.PositiveIntegerField(verbose_name="序号")),
                ("stage", models.CharField(max_length=50, verbose_name="业务阶段")),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("system", "系统"),
                            ("tool", "工具"),
                            ("model", "模型"),
                            ("rag", "RAG"),
                        ],
                        default="system",
                        max_length=20,
                        verbose_name="事件类型",
                    ),
                ),
                ("tool", models.CharField(max_length=100, verbose_name="工具")),
                ("status", models.CharField(max_length=20, verbose_name="状态")),
                ("title", models.CharField(max_length=160, verbose_name="标题")),
                ("detail", models.TextField(blank=True, verbose_name="说明")),
                (
                    "metadata",
                    models.JSONField(blank=True, default=dict, verbose_name="结构化信息"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="发生时间")),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow_events",
                        to="document_generation.generationtask",
                        verbose_name="生成任务",
                    ),
                ),
            ],
            options={
                "verbose_name": "四措两案工作流事件",
                "verbose_name_plural": "四措两案工作流事件",
                "ordering": ["sequence", "id"],
                "indexes": [
                    models.Index(
                        fields=["task", "sequence"],
                        name="docgen_trace_task_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("task", "sequence"),
                        name="docgen_trace_task_seq_uq",
                    ),
                ],
            },
        ),
    ]
