from typing import Any
from urllib.parse import quote

from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import TemporaryAccessGrant
from .selectors import manageable_document_ids_for_user
from .temporary_serializers import (
    TemporaryAccessGrantCreatedSerializer,
    TemporaryAccessGrantCreateSerializer,
    TemporaryAccessGrantSerializer,
)
from .temporary_services import (
    consume_temporary_access_token,
    create_temporary_access_grant,
    revoke_temporary_access_grant,
)


class TemporaryAccessGrantViewSet(viewsets.ModelViewSet):
    queryset = TemporaryAccessGrant.objects.none()
    serializer_class = TemporaryAccessGrantSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["document_version", "revoked_at"]
    ordering_fields = ["created_at", "expires_at", "last_used_at"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TemporaryAccessGrant.objects.none()
        manageable_document_ids = manageable_document_ids_for_user(self.request.user).values("id")
        return TemporaryAccessGrant.objects.select_related(
            "document_version",
            "document_version__document",
            "created_by",
            "revoked_by",
        ).filter(document_version__document_id__in=manageable_document_ids)

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def get_serializer_class(self):
        if self.action == "create":
            return TemporaryAccessGrantCreateSerializer
        return TemporaryAccessGrantSerializer

    @extend_schema(
        request=TemporaryAccessGrantCreateSerializer,
        responses=TemporaryAccessGrantCreatedSerializer,
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = create_temporary_access_grant(
            actor=request.user,
            document_version=serializer.validated_data["document_version"],
            expires_at=serializer.validated_data.get("expires_at"),
            max_downloads=serializer.validated_data["max_downloads"],
            request=request,
        )
        response_serializer = TemporaryAccessGrantCreatedSerializer(
            result.grant,
            context={"request": request, "token": result.token},
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=TemporaryAccessGrantSerializer)
    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        grant = revoke_temporary_access_grant(
            actor=request.user,
            grant=self.get_object(),
            request=request,
        )
        return Response(TemporaryAccessGrantSerializer(grant).data)


@extend_schema(request=None, responses={200: bytes})
@api_view(["GET"])
@permission_classes([AllowAny])
def temporary_access_download(request: Any, token: str) -> FileResponse:
    file_handle, version = consume_temporary_access_token(token=token, request=request)
    response = FileResponse(
        file_handle,
        as_attachment=True,
        content_type=version.content_type or "application/octet-stream",
    )
    filename = quote(version.original_filename)
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{filename}"
    response["Content-Length"] = str(version.file_size)
    return response
