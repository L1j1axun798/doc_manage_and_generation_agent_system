from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        SYSTEM_ADMIN = "system_admin", "系统管理员"
        PROJECT_MANAGER = "project_manager", "项目负责人"
        DATA_OPERATOR = "data_operator", "资料整理员"

    real_name = models.CharField("真实姓名", max_length=80)
    employee_no = models.CharField("员工编号", max_length=50, unique=True, null=True, blank=True)
    role = models.CharField("角色", max_length=32, choices=Role.choices, default=Role.DATA_OPERATOR)
    phone = models.CharField("手机号", max_length=30, blank=True)
    must_change_password = models.BooleanField("首次登录需修改密码", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

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
