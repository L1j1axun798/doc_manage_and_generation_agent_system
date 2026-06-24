from rest_framework.routers import DefaultRouter

from .views import DocumentGrantViewSet

router = DefaultRouter()
router.register("document-grants", DocumentGrantViewSet, basename="document-grant")

urlpatterns = router.urls
