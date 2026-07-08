from django.urls import path

from .views import (
    AdminLatestLocationsView,
    LocationReportChallengeView,
    LocationReportView,
    MyLatestLocationView,
)

urlpatterns = [
    path(
        "locations/report/challenge/",
        LocationReportChallengeView.as_view(),
        name="locations-report-challenge",
    ),
    path("locations/report/", LocationReportView.as_view(), name="locations-report"),
    path("locations/me/latest/", MyLatestLocationView.as_view(), name="locations-me-latest"),
    path(
        "locations/admin/latest/",
        AdminLatestLocationsView.as_view(),
        name="locations-admin-latest",
    ),
]
