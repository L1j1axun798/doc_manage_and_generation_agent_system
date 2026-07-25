from django.urls import include, path

urlpatterns = [
    path("", include("apps.accounts.urls")),
    path("", include("apps.access.urls")),
    path("", include("apps.audit.urls")),
    path("", include("apps.documents.urls")),
    path("", include("apps.document_generation.urls")),
    path("", include("apps.folders.urls")),
    path("", include("apps.locations.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.projects.urls")),
    path("", include("apps.system.urls")),
]
