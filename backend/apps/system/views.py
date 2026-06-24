from django.conf import settings
from django.http import HttpRequest
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


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
