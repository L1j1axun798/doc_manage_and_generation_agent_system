from django.urls import path

from .views import HealthCheckView

app_name = "system"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
]
