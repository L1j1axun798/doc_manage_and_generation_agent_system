from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsSystemAdmin

from .models import Folder
from .personnel import personnel_folders, update_personnel_profile
from .selectors import active_visible_folders_for_user, folder_tree_for_user
from .serializers import (
    FolderMoveSerializer,
    FolderSerializer,
    PersonnelRecordSerializer,
    PersonnelRecordUpdateSerializer,
)
from .services import create_folder, disable_folder, move_folder, update_folder


class FolderViewSet(viewsets.ModelViewSet):
    queryset = Folder.objects.none()
    serializer_class = FolderSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    search_fields = ["name", "code", "project__name", "parent__name"]
    ordering_fields = ["sort_order", "name", "created_at", "updated_at"]
    ordering = ["sort_order", "id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Folder.objects.none()
        return active_visible_folders_for_user(self.request.user)

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def perform_create(self, serializer):
        serializer.instance = create_folder(
            actor=self.request.user,
            data=dict(serializer.validated_data),
            request=self.request,
        )

    def perform_update(self, serializer):
        serializer.instance = update_folder(
            actor=self.request.user,
            folder=self.get_object(),
            data=dict(serializer.validated_data),
            request=self.request,
        )

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=["get"])
    def tree(self, request):
        return Response(folder_tree_for_user(request.user, request.query_params.get("project_id")))

    @extend_schema(request=FolderMoveSerializer, responses=FolderSerializer)
    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        folder = self.get_object()
        serializer = FolderMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        folder = move_folder(
            actor=request.user,
            folder=folder,
            parent=serializer.validated_data.get("parent"),
            sort_order=serializer.validated_data.get("sort_order"),
            request=request,
        )
        return Response(FolderSerializer(folder).data)

    @extend_schema(request=None, responses={204: OpenApiResponse(description="文件夹已停用")})
    @action(detail=True, methods=["post"])
    def disable(self, request, pk=None):
        disable_folder(actor=request.user, folder=self.get_object(), request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PersonnelViewSet(viewsets.GenericViewSet):
    queryset = Folder.objects.none()
    serializer_class = PersonnelRecordSerializer
    permission_classes = [IsSystemAdmin]
    http_method_names = ["get", "put", "patch", "head", "options"]
    search_fields = ["name", "personnel_profile__id_card_number", "personnel_profile__phone"]
    ordering_fields = ["name", "sort_order", "personnel_profile__updated_at"]
    ordering = ["sort_order", "id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Folder.objects.none()
        return personnel_folders()

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(PersonnelRecordSerializer(page, many=True).data)
        return Response(PersonnelRecordSerializer(queryset, many=True).data)

    def retrieve(self, request, pk=None):
        return Response(PersonnelRecordSerializer(self.get_object()).data)

    def update(self, request, pk=None):
        serializer = PersonnelRecordUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        folder = self.get_object()
        update_personnel_profile(
            actor=request.user,
            folder=folder,
            data=dict(serializer.validated_data),
            request=request,
        )
        folder = personnel_folders().get(pk=folder.pk)
        return Response(PersonnelRecordSerializer(folder).data)

    def partial_update(self, request, pk=None):
        return self.update(request, pk=pk)
