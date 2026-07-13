import hashlib
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        SYSTEM_ADMIN = "system_admin", "系统管理员"
        PROJECT_MANAGER = "project_manager", "项目负责人"
        DATA_OPERATOR = "data_operator", "资料整理员"
        TEMPORARY_USER = "temporary_user", "临时用户"

    real_name = models.CharField("真实姓名", max_length=80)
    employee_no = models.CharField("员工编号", max_length=50, unique=True, null=True, blank=True)
    role = models.CharField("角色", max_length=32, choices=Role.choices, default=Role.DATA_OPERATOR)
    phone = models.CharField("手机号", max_length=30, blank=True)
    must_change_password = models.BooleanField("首次登录需修改密码", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    REQUIRED_FIELDS = ["real_name", "email"]

    class Meta:
        indexes = [
            models.Index(fields=["role"], name="accounts_user_role_idx"),
            models.Index(fields=["is_active"], name="accounts_user_active_idx"),
        ]
        verbose_name = "用户"
        verbose_name_plural = "用户"

    @property
    def is_system_admin(self) -> bool:
        return self.is_superuser or self.role == self.Role.SYSTEM_ADMIN

    @property
    def is_temporary_user(self) -> bool:
        return self.role == self.Role.TEMPORARY_USER


class WebAuthnCredential(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="webauthn_credentials",
        verbose_name="用户",
    )
    name = models.CharField("设备名称", max_length=120, blank=True)
    credential_id = models.TextField("凭据 ID")
    credential_id_hash = models.CharField("凭据 ID 哈希", max_length=64, unique=True)
    public_key = models.BinaryField("公钥")
    sign_count = models.PositiveIntegerField("签名计数", default=0)
    transports = models.JSONField("传输方式", default=list, blank=True)
    device_type = models.CharField("设备类型", max_length=50, blank=True)
    backed_up = models.BooleanField("是否已备份", default=False)
    aaguid = models.CharField("AAGUID", max_length=64, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    last_used_at = models.DateTimeField("最近使用时间", null=True, blank=True)
    revoked_at = models.DateTimeField("撤销时间", null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_webauthn_credentials",
        verbose_name="撤销人",
    )

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"], name="webauthn_cred_user_active_idx"),
            models.Index(fields=["created_at"], name="webauthn_cred_created_idx"),
        ]
        verbose_name = "WebAuthn 凭据"
        verbose_name_plural = "WebAuthn 凭据"

    def __str__(self) -> str:
        return f"{self.user_id}:{self.name or self.credential_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.credential_id_hash = hashlib.sha256(self.credential_id.encode("utf-8")).hexdigest()
        super().save(*args, **kwargs)

    def revoke(self, *, actor: "User") -> None:
        self.is_active = False
        self.revoked_at = timezone.now()
        self.revoked_by = actor
        self.save(update_fields=["is_active", "revoked_at", "revoked_by"])


class WebAuthnEnrollmentTicket(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="webauthn_enrollment_tickets",
        verbose_name="用户",
    )
    token_hash = models.CharField("绑定票据哈希", max_length=64, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_webauthn_enrollment_tickets",
        verbose_name="创建人",
    )
    expires_at = models.DateTimeField("过期时间")
    used_at = models.DateTimeField("使用时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "expires_at"], name="webauthn_ticket_user_exp_idx"),
            models.Index(fields=["created_at"], name="webauthn_ticket_created_idx"),
        ]
        verbose_name = "WebAuthn 绑定票据"
        verbose_name_plural = "WebAuthn 绑定票据"

    def __str__(self) -> str:
        return f"{self.user_id}:{self.expires_at:%Y-%m-%d %H:%M:%S}"

    @property
    def is_available(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class WebAuthnChallenge(models.Model):
    class Purpose(models.TextChoices):
        LOGIN = "login", "登录"
        REGISTER = "register", "绑定"
        LOCATION = "location", "定位"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="webauthn_challenges",
        verbose_name="用户",
    )
    purpose = models.CharField("用途", max_length=32, choices=Purpose.choices)
    challenge = models.CharField("Challenge", max_length=255)
    token_hash = models.CharField("挑战票据哈希", max_length=64, unique=True)
    metadata = models.JSONField("附加数据", default=dict, blank=True)
    expires_at = models.DateTimeField("过期时间")
    used_at = models.DateTimeField("使用时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "purpose", "expires_at"],
                name="webauthn_chal_user_exp_idx",
            ),
            models.Index(fields=["created_at"], name="webauthn_chal_created_idx"),
        ]
        verbose_name = "WebAuthn 挑战"
        verbose_name_plural = "WebAuthn 挑战"

    def __str__(self) -> str:
        return f"{self.user_id}:{self.purpose}:{self.expires_at:%Y-%m-%d %H:%M:%S}"

    @property
    def is_available(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()
