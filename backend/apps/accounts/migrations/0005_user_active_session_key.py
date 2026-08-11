from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_webauthn_credential_hash"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="active_session_key",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=40,
                null=True,
                verbose_name="当前登录会话键",
            ),
        ),
    ]
