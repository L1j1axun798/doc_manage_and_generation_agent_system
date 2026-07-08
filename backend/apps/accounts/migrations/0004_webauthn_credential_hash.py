import hashlib

from django.db import migrations, models


def populate_credential_hashes(apps, schema_editor):
    credential_model = apps.get_model("accounts", "WebAuthnCredential")
    for credential in credential_model.objects.all():
        credential.credential_id_hash = hashlib.sha256(
            credential.credential_id.encode("utf-8")
        ).hexdigest()
        credential.save(update_fields=["credential_id_hash"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_webauthn"),
    ]

    operations = [
        migrations.AddField(
            model_name="webauthncredential",
            name="credential_id_hash",
            field=models.CharField(
                blank=True,
                max_length=64,
                null=True,
                verbose_name="凭据 ID 哈希",
            ),
        ),
        migrations.RunPython(populate_credential_hashes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="webauthncredential",
            name="credential_id",
            field=models.TextField(verbose_name="凭据 ID"),
        ),
        migrations.AlterField(
            model_name="webauthncredential",
            name="credential_id_hash",
            field=models.CharField(max_length=64, unique=True, verbose_name="凭据 ID 哈希"),
        ),
    ]
