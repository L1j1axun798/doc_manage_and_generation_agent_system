from rest_framework.routers import DefaultRouter

from .views import FolderViewSet, PersonnelViewSet

router = DefaultRouter()
router.register("folders", FolderViewSet, basename="folder")
router.register("personnel", PersonnelViewSet, basename="personnel")

urlpatterns = router.urls
