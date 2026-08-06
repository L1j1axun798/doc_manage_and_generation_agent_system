from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Project, ProjectMember
from .permissions import can_manage_project, can_manage_project_members
from .selectors import project_members_for_project, visible_projects_for_user
from .serializers import ProjectMemberSerializer, ProjectSerializer
from .services import (
    archive_project,
    create_project,
    create_project_member,
    delete_project,
    delete_project_member,
    unarchive_project,
    update_project,
    update_project_member,
)


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.none()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Project.objects.none()
        return visible_projects_for_user(self.request.user)

    def perform_create(self, serializer):
        serializer.instance = create_project(
            actor=self.request.user,
            data=dict(serializer.validated_data),
            request=self.request,
        )

    def perform_update(self, serializer):
        project = self.get_object()
        if not can_manage_project(self.request.user, project):
            raise PermissionDenied("无权修改该项目")
        serializer.instance = update_project(
            actor=self.request.user,
            project=project,
            data=dict(serializer.validated_data),
            request=self.request,
        )

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()
        if not getattr(request.user, "is_system_admin", False):
            raise PermissionDenied("只有系统管理员可以删除项目")
        delete_project(actor=request.user, project=project, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses=ProjectSerializer)
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        project = self.get_object()
        if not can_manage_project(request.user, project):
            raise PermissionDenied("无权归档该项目")
        project = archive_project(actor=request.user, project=project, request=request)
        return Response(ProjectSerializer(project).data)

    @extend_schema(request=None, responses=ProjectSerializer)
    @action(detail=True, methods=["post"])
    def unarchive(self, request, pk=None):
        project = self.get_object()
        if not getattr(request.user, "is_system_admin", False):
            raise PermissionDenied("只有系统管理员可以取消归档")
        project = unarchive_project(actor=request.user, project=project, request=request)
        return Response(ProjectSerializer(project).data)


class ProjectMemberViewSet(viewsets.ModelViewSet):
    queryset = ProjectMember.objects.none()
    serializer_class = ProjectMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_project(self) -> Project:
        return get_object_or_404(
            visible_projects_for_user(self.request.user),
            pk=self.kwargs["project_pk"],
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action in {"create", "update", "partial_update"}:
            context["project"] = self.get_project()
        return context

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ProjectMember.objects.none()
        project = self.get_project()
        if not can_manage_project_members(self.request.user, project):
            raise PermissionDenied("无权管理项目成员")
        return project_members_for_project(project)

    def perform_create(self, serializer):
        project = self.get_project()
        if not can_manage_project_members(self.request.user, project):
            raise PermissionDenied("无权管理项目成员")
        serializer.instance = create_project_member(
            actor=self.request.user,
            project=project,
            data=dict(serializer.validated_data),
            request=self.request,
        )

    def perform_update(self, serializer):
        member = self.get_object()
        if not can_manage_project_members(self.request.user, member.project):
            raise PermissionDenied("无权管理项目成员")
        serializer.instance = update_project_member(
            actor=self.request.user,
            member=member,
            data=dict(serializer.validated_data),
            request=self.request,
        )

    def destroy(self, request, *args, **kwargs):
        member = self.get_object()
        if not can_manage_project_members(request.user, member.project):
            raise PermissionDenied("无权管理项目成员")
        delete_project_member(actor=request.user, member=member, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
