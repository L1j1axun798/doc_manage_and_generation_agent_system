from urllib.parse import quote

from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Document
from .selectors import base_documents_for_user, visible_documents_for_user
from .serializers import (
    DocumentSerializer,
    DocumentUploadSerializer,
    DocumentVersionSerializer,
    DocumentVersionUploadSerializer,
)
from .services import create_document, create_document_version, open_current_version_for_download


class DocumentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Document.objects.none()
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "folder", "access_level"]
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

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def get_base_scoped_object(self):
        return get_object_or_404(base_documents_for_user(self.request.user), pk=self.kwargs["pk"])

    def get_serializer_class(self):
        if self.action == "create":
            return DocumentUploadSerializer
        if self.action == "versions":
            return DocumentVersionUploadSerializer
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
