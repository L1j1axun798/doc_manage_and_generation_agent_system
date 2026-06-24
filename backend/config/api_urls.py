from django.urls import include, path

urlpatterns = [
    path("", include("apps.accounts.urls")),
    path("", include("apps.documents.urls")),
    path("", include("apps.folders.urls")),
    path("", include("apps.projects.urls")),
    path("", include("apps.system.urls")),
]
