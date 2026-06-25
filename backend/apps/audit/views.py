from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, viewsets

from apps.accounts.permissions import IsSystemAdmin

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AuditLog.objects.select_related("user")
    serializer_class = AuditLogSerializer
    permission_classes = [IsSystemAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["user", "action", "resource_type", "resource_id", "result"]
    search_fields = ["action", "resource_type", "resource_id", "error_message", "request_id"]
    ordering_fields = ["created_at", "id"]
    ordering = ["-created_at", "-id"]
