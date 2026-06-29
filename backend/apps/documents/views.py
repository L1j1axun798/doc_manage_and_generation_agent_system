from urllib.parse import quote

from django.db.models import Q
from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.folders.defaults import ARCHIVE_ROOT, standard_root_for_code, standard_root_for_name
from apps.folders.models import Folder

from .models import Document
from .selectors import (
    base_documents_for_user,
    trashed_documents_for_user,
    visible_documents_for_user,
)
from .serializers import (
    DocumentBatchDownloadSerializer,
    DocumentMoveSerializer,
    DocumentMutationSerializer,
    DocumentSerializer,
    DocumentUpdateSerializer,
    DocumentUploadSerializer,
    DocumentVersionSerializer,
    DocumentVersionUploadSerializer,
)
from .services import (
    build_batch_download_zip,
    create_document,
    create_document_version,
    move_document,
    open_current_version_for_download,
    permanently_delete_document,
    restore_document,
    soft_delete_document,
    update_document_metadata,
)


class DocumentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Document.objects.none()
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "access_level"]
    search_fields = [
        "title",
        "description",
        "current_version__original_filename",
        "current_version__sha256",
    ]
    ordering_fields = ["created_at", "updated_at", "title"]
    ordering = ["-updated_at", "-id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Document.objects.none()
        return visible_documents_for_user(self.request.user)

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        folder_id = self.request.query_params.get("folder")
        if not folder_id:
            return queryset
        return queryset.filter(folder_id__in=descendant_folder_ids(folder_id))

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def get_base_scoped_object(self):
        return get_object_or_404(base_documents_for_user(self.request.user), pk=self.kwargs["pk"])

    def get_deleted_scoped_object(self):
        return get_object_or_404(
            base_documents_for_user(self.request.user, include_deleted=True),
            pk=self.kwargs["pk"],
        )

    def get_serializer_class(self):
        if self.action == "create":
            return DocumentUploadSerializer
        if self.action == "versions":
            return DocumentVersionUploadSerializer
        if self.action in {"update", "partial_update"}:
            return DocumentUpdateSerializer
        if self.action == "move":
            return DocumentMoveSerializer
        if self.action in {"delete", "restore", "permanent_delete"}:
            return DocumentMutationSerializer
        if self.action == "batch_download":
            return DocumentBatchDownloadSerializer
        return DocumentSerializer

    @extend_schema(request=DocumentUploadSerializer, responses=DocumentSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = create_document(
            actor=request.user,
            folder=serializer.validated_data["folder"],
            uploaded_file=serializer.validated_data["file"],
            title=serializer.validated_data.get("title", ""),
            description=serializer.validated_data.get("description", ""),
            access_level=serializer.validated_data.get(
                "access_level",
                Document.AccessLevel.INTERNAL,
            ),
            request=request,
        )
        return Response(DocumentSerializer(document).data, status=201)

    @extend_schema(request=DocumentVersionUploadSerializer, responses=DocumentVersionSerializer)
    @action(detail=True, methods=["post"], url_path="versions")
    def versions(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = create_document_version(
            actor=request.user,
            document=self.get_object(),
            uploaded_file=serializer.validated_data["file"],
            request=request,
        )
        return Response(DocumentVersionSerializer(version).data, status=201)

    @extend_schema(request=DocumentUpdateSerializer, responses=DocumentSerializer)
    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = dict(serializer.validated_data)
        expected_updated_at = validated_data.pop("expected_updated_at")
        document = update_document_metadata(
            actor=request.user,
            document=self.get_object(),
            data=validated_data,
            expected_updated_at=expected_updated_at,
            request=request,
        )
        return Response(DocumentSerializer(document).data)

    @extend_schema(request=DocumentUpdateSerializer, responses=DocumentSerializer)
    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @extend_schema(request=DocumentMoveSerializer, responses=DocumentSerializer)
    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = move_document(
            actor=request.user,
            document=self.get_object(),
            folder=serializer.validated_data["folder"],
            expected_updated_at=serializer.validated_data["expected_updated_at"],
            request=request,
        )
        return Response(DocumentSerializer(document).data)

    @extend_schema(request=DocumentMutationSerializer, responses={204: None})
    @action(detail=True, methods=["post"])
    def delete(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        soft_delete_document(
            actor=request.user,
            document=self.get_object(),
            expected_updated_at=serializer.validated_data["expected_updated_at"],
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=DocumentMutationSerializer, responses=DocumentSerializer)
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = restore_document(
            actor=request.user,
            document=self.get_deleted_scoped_object(),
            expected_updated_at=serializer.validated_data["expected_updated_at"],
            request=request,
        )
        return Response(DocumentSerializer(document).data)

    @extend_schema(request=DocumentMutationSerializer, responses={204: None})
    @action(detail=True, methods=["post"], url_path="permanent-delete")
    def permanent_delete(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permanently_delete_document(
            actor=request.user,
            document=self.get_deleted_scoped_object(),
            expected_updated_at=serializer.validated_data["expected_updated_at"],
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses=DocumentSerializer(many=True))
    @action(detail=False, methods=["get"])
    def trash(self, request):
        queryset = self.filter_queryset(trashed_documents_for_user(request.user))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DocumentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(DocumentSerializer(queryset, many=True).data)

    @extend_schema(request=DocumentBatchDownloadSerializer, responses={200: bytes})
    @action(detail=False, methods=["post"], url_path="batch-download")
    def batch_download(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_ids = serializer.validated_data["document_ids"]
        documents = list(
            base_documents_for_user(request.user)
            .filter(pk__in=document_ids)
            .select_related("current_version")
        )
        if len(documents) != len(set(document_ids)):
            return Response(
                {"detail": "批量下载包含不存在或不可见的文档"},
                status=status.HTTP_403_FORBIDDEN,
            )
        document_by_id = {document.pk: document for document in documents}
        ordered_documents = [document_by_id[document_id] for document_id in document_ids]
        archive, filename, total_size = build_batch_download_zip(
            actor=request.user,
            documents=ordered_documents,
            request=request,
        )
        response = FileResponse(
            archive,
            as_attachment=True,
            content_type="application/zip",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-Archive-Uncompressed-Size"] = str(total_size)
        return response

    @extend_schema(request=None, responses={200: bytes})
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_base_scoped_object()
        file_handle, version = open_current_version_for_download(
            actor=request.user,
            document=document,
            request=request,
        )
        response = FileResponse(
            file_handle,
            as_attachment=True,
            content_type=version.content_type or "application/octet-stream",
        )
        filename = quote(version.original_filename)
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{filename}"
        response["Content-Length"] = str(version.file_size)
        return response


def descendant_folder_ids(raw_folder_id: str) -> list[int]:
    try:
        folder_id = int(raw_folder_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError({"folder": "目录参数必须是整数"}) from exc

    folder = Folder.objects.filter(pk=folder_id, is_active=True).first()
    if folder is None:
        return [folder_id]

    root_ids = [folder_id]
    if folder.project_id is None and folder.parent_id is None:
        definition = standard_root_for_code(folder.code) or standard_root_for_name(folder.name)
        if definition is not None:
            equivalent_root_ids = Folder.objects.filter(
                Q(code=definition.code) | Q(name__in=definition.names),
                is_active=True,
            ).values_list("id", flat=True)
            root_ids.extend(equivalent_root_ids)
        elif folder.code == ARCHIVE_ROOT.code or folder.name in ARCHIVE_ROOT.names:
            root_ids.extend(
                Folder.objects.filter(
                    is_active=True,
                    project__isnull=True,
                    parent=folder,
                ).values_list("id", flat=True)
            )

    folder_ids = list(dict.fromkeys(root_ids))
    frontier = folder_ids.copy()
    while frontier:
        child_ids = list(
            Folder.objects.filter(parent_id__in=frontier, is_active=True).values_list(
                "id",
                flat=True,
            )
        )
        frontier = [child_id for child_id in child_ids if child_id not in folder_ids]
        folder_ids.extend(frontier)
    return folder_ids
