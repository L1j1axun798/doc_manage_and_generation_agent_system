from django.conf import settings
from django.http import HttpRequest
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSystemAdmin

from .models import SystemBackupRun
from .serializers import SystemBackupRunSerializer


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: HttpRequest) -> Response:
        return Response(
            {
                "status": "ok",
                "service": "wind-doc-system-backend",
                "debug": settings.DEBUG,
                "request_id": getattr(request, "request_id", None),
            }
        )


class SystemBackupRunViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = SystemBackupRun.objects.select_related("created_by")
    serializer_class = SystemBackupRunSerializer
    permission_classes = [IsSystemAdmin]
    ordering = ["-started_at", "-id"]

    @extend_schema(responses={200: SystemBackupRunSerializer, 204: None})
    @action(detail=False, methods=["get"])
    def latest(self, request: HttpRequest) -> Response:
        backup_run = self.get_queryset().first()
        if backup_run is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(self.get_serializer(backup_run).data)
