# Generated manually for WebAuthn login and location verification.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_temporary_role"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WebAuthnCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=120, verbose_name="设备名称")),
                ("credential_id", models.CharField(max_length=512, unique=True, verbose_name="凭据 ID")),
                ("public_key", models.BinaryField(verbose_name="公钥")),
                ("sign_count", models.PositiveIntegerField(default=0, verbose_name="签名计数")),
                ("transports", models.JSONField(blank=True, default=list, verbose_name="传输方式")),
                ("device_type", models.CharField(blank=True, max_length=50, verbose_name="设备类型")),
                ("backed_up", models.BooleanField(default=False, verbose_name="是否已备份")),
                ("aaguid", models.CharField(blank=True, max_length=64, verbose_name="AAGUID")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("last_used_at", models.DateTimeField(blank=True, null=True, verbose_name="最近使用时间")),
                ("revoked_at", models.DateTimeField(blank=True, null=True, verbose_name="撤销时间")),
                (
                    "revoked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="revoked_webauthn_credentials",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="撤销人",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="webauthn_credentials",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "WebAuthn 凭据",
                "verbose_name_plural": "WebAuthn 凭据",
            },
        ),
        migrations.CreateModel(
            name="WebAuthnEnrollmentTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(max_length=64, unique=True, verbose_name="绑定票据哈希")),
                ("expires_at", models.DateTimeField(verbose_name="过期时间")),
                ("used_at", models.DateTimeField(blank=True, null=True, verbose_name="使用时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_webauthn_enrollment_tickets",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="创建人",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="webauthn_enrollment_tickets",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "WebAuthn 绑定票据",
                "verbose_name_plural": "WebAuthn 绑定票据",
            },
        ),
        migrations.CreateModel(
            name="WebAuthnChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "purpose",
                    models.CharField(
                        choices=[("login", "登录"), ("register", "绑定"), ("location", "定位")],
                        max_length=32,
                        verbose_name="用途",
                    ),
                ),
                ("challenge", models.CharField(max_length=255, verbose_name="Challenge")),
                ("token_hash", models.CharField(max_length=64, unique=True, verbose_name="挑战票据哈希")),
                ("metadata", models.JSONField(blank=True, default=dict, verbose_name="附加数据")),
                ("expires_at", models.DateTimeField(verbose_name="过期时间")),
                ("used_at", models.DateTimeField(blank=True, null=True, verbose_name="使用时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="webauthn_challenges",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "WebAuthn 挑战",
                "verbose_name_plural": "WebAuthn 挑战",
            },
        ),
        migrations.AddIndex(
            model_name="webauthncredential",
            index=models.Index(fields=["user", "is_active"], name="webauthn_cred_user_active_idx"),
        ),
        migrations.AddIndex(
            model_name="webauthncredential",
            index=models.Index(fields=["created_at"], name="webauthn_cred_created_idx"),
        ),
        migrations.AddIndex(
            model_name="webauthnenrollmentticket",
            index=models.Index(fields=["user", "expires_at"], name="webauthn_ticket_user_exp_idx"),
        ),
        migrations.AddIndex(
            model_name="webauthnenrollmentticket",
            index=models.Index(fields=["created_at"], name="webauthn_ticket_created_idx"),
        ),
        migrations.AddIndex(
            model_name="webauthnchallenge",
            index=models.Index(fields=["user", "purpose", "expires_at"], name="webauthn_chal_user_exp_idx"),
        ),
        migrations.AddIndex(
            model_name="webauthnchallenge",
            index=models.Index(fields=["created_at"], name="webauthn_chal_created_idx"),
        ),
    ]
