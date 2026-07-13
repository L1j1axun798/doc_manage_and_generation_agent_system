from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import HealthCheckView, SystemBackupRunViewSet

app_name = "system"

router = DefaultRouter()
router.register("system/backups", SystemBackupRunViewSet, basename="system-backup")

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    *router.urls,
]
