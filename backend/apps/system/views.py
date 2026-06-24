from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(
            {
                "status": "ok",
                "service": "wind-doc-system-backend",
                "debug": settings.DEBUG,
                "request_id": getattr(request, "request_id", None),
            }
        )
