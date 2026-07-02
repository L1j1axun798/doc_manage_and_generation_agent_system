from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSystemAdmin
from apps.audit.services import audit_log

from .serializers import (
    LocationReportRequestSerializer,
    LocationReportSerializer,
    LocationSnapshotSerializer,
)
from .services import build_location_snapshot, get_admin_location_snapshots, get_latest_report


class LocationReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=LocationReportRequestSerializer, responses=LocationReportSerializer)
    def post(self, request):
        serializer = LocationReportRequestSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        audit_log(
            user=request.user,
            action="location.report",
            resource=report,
            result="success",
            request=request,
            after_data={"report_status": report.report_status},
        )
        return Response(LocationReportSerializer(report).data, status=201)


class MyLatestLocationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=LocationSnapshotSerializer)
    def get(self, request):
        snapshot = build_location_snapshot(
            user=request.user,
            latest_report=get_latest_report(request.user),
        )
        return Response(LocationSnapshotSerializer(snapshot).data)


class AdminLatestLocationsView(APIView):
    permission_classes = [IsSystemAdmin]

    @extend_schema(responses=LocationSnapshotSerializer(many=True))
    def get(self, request):
        snapshots = get_admin_location_snapshots()
        return Response(LocationSnapshotSerializer(snapshots, many=True).data)
