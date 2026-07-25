from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DocumentTemplateViewSet, GenerationTaskViewSet

router = DefaultRouter()
router.register(
    "document-generation/templates",
    DocumentTemplateViewSet,
    basename="docgen-template",
)
router.register("document-generation/tasks", GenerationTaskViewSet, basename="docgen-task")

section_detail = GenerationTaskViewSet.as_view({"patch": "update_section"})
section_lock = GenerationTaskViewSet.as_view({"post": "lock_section"})
section_regenerate = GenerationTaskViewSet.as_view({"post": "regenerate_section"})

urlpatterns = [
    path("", include(router.urls)),
    path(
        "document-generation/tasks/<uuid:pk>/sections/<str:section_code>/",
        section_detail,
        name="docgen-section-detail",
    ),
    path(
        "document-generation/tasks/<uuid:pk>/sections/<str:section_code>/lock/",
        section_lock,
        name="docgen-section-lock",
    ),
    path(
        "document-generation/tasks/<uuid:pk>/sections/<str:section_code>/regenerate/",
        section_regenerate,
        name="docgen-section-regenerate",
    ),
]
