from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import DocumentGrant
from .selectors import grants_manageable_by_user
from .serializers import DocumentGrantSerializer, DocumentGrantUpdateSerializer
from .services import create_document_grant, revoke_document_grant, update_document_grant


class DocumentGrantViewSet(viewsets.ModelViewSet):
    queryset = DocumentGrant.objects.none()
    serializer_class = DocumentGrantSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["document", "user", "revoked_at"]
    ordering_fields = ["created_at", "expires_at", "updated_at"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DocumentGrant.objects.none()
        return grants_manageable_by_user(self.request.user)

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return DocumentGrantUpdateSerializer
        return DocumentGrantSerializer

    def perform_create(self, serializer):
        serializer.instance = create_document_grant(
            actor=self.request.user,
            document=serializer.validated_data["document"],
            data={
                key: value for key, value in serializer.validated_data.items() if key != "document"
            },
            request=self.request,
        )

    def perform_update(self, serializer):
        serializer.instance = update_document_grant(
            actor=self.request.user,
            grant=self.get_object(),
            data=dict(serializer.validated_data),
            request=self.request,
        )

    @extend_schema(request=None, responses=DocumentGrantSerializer)
    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        grant = revoke_document_grant(
            actor=request.user,
            grant=self.get_object(),
            request=request,
        )
        return Response(DocumentGrantSerializer(grant).data, status=status.HTTP_200_OK)
