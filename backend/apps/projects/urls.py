from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProjectMemberViewSet, ProjectViewSet

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")

member_list = ProjectMemberViewSet.as_view(
    {
        "get": "list",
        "post": "create",
    }
)
member_detail = ProjectMemberViewSet.as_view(
    {
        "get": "retrieve",
        "patch": "partial_update",
        "put": "update",
        "delete": "destroy",
    }
)

urlpatterns = [
    path("", include(router.urls)),
    path("projects/<int:project_pk>/members/", member_list, name="project-member-list"),
    path(
        "projects/<int:project_pk>/members/<int:pk>/",
        member_detail,
        name="project-member-detail",
    ),
]
