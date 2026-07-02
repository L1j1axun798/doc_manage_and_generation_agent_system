from django.urls import path

from .views import AdminLatestLocationsView, LocationReportView, MyLatestLocationView

urlpatterns = [
    path("locations/report/", LocationReportView.as_view(), name="locations-report"),
    path("locations/me/latest/", MyLatestLocationView.as_view(), name="locations-me-latest"),
    path(
        "locations/admin/latest/",
        AdminLatestLocationsView.as_view(),
        name="locations-admin-latest",
    ),
]
