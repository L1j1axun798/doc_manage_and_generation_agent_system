from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("document_generation", "0007_knowledgecorpusupload_multisection"),
    ]

    operations = [
        migrations.AddField(
            model_name="generationtask",
            name="conversation_context",
            field=models.JSONField(default=dict, verbose_name="会话上下文快照"),
        ),
    ]
