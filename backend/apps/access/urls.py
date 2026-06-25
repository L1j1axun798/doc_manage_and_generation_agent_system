from django.urls import path
from rest_framework.routers import DefaultRouter

from .temporary_views import TemporaryAccessGrantViewSet, temporary_access_download
from .views import DocumentGrantViewSet

router = DefaultRouter()
router.register("document-grants", DocumentGrantViewSet, basename="document-grant")
router.register(
    "temporary-access-grants",
    TemporaryAccessGrantViewSet,
    basename="temporary-access-grant",
)

urlpatterns = [
    *router.urls,
    path(
        "temporary-access/<str:token>/download/",
        temporary_access_download,
        name="temporary-access-download",
    ),
]
