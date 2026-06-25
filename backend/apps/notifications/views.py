from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .selectors import notifications_for_user
from .serializers import NotificationSerializer
from .services import mark_notification_read, mark_notification_unread


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["is_read", "category"]
    ordering_fields = ["created_at", "read_at"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return notifications_for_user(self.request.user)

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    @extend_schema(request=None, responses=NotificationSerializer)
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = mark_notification_read(
            actor=request.user,
            notification=self.get_object(),
            request=request,
        )
        return Response(NotificationSerializer(notification).data)

    @extend_schema(request=None, responses=NotificationSerializer)
    @action(detail=True, methods=["post"])
    def unread(self, request, pk=None):
        notification = mark_notification_unread(
            actor=request.user,
            notification=self.get_object(),
            request=request,
        )
        return Response(NotificationSerializer(notification).data)
