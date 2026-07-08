from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSystemAdmin
from apps.accounts.serializers import WebAuthnOptionsResponseSerializer
from apps.accounts.webauthn_services import begin_location_challenge, verify_location_challenge
from apps.audit.services import audit_log

from .serializers import (
    LocationReportRequestSerializer,
    LocationReportSerializer,
    LocationSnapshotSerializer,
    location_payload_hash,
)
from .services import build_location_snapshot, get_admin_location_snapshots, get_latest_report


class LocationReportChallengeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LocationReportRequestSerializer,
        responses=WebAuthnOptionsResponseSerializer,
    )
    def post(self, request):
        serializer = LocationReportRequestSerializer(
            data=request.data,
            context={"request": request, "require_webauthn": False},
        )
        serializer.is_valid(raise_exception=True)
        result = begin_location_challenge(
            user=request.user,
            payload_hash=location_payload_hash(serializer.validated_data),
            request=request,
        )
        return Response({"token": result.token, "options": result.options})


class LocationReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=LocationReportRequestSerializer, responses=LocationReportSerializer)
    def post(self, request):
        serializer = LocationReportRequestSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        webauthn = serializer.validated_data.get("webauthn") or {}
        credential = webauthn.get("credential")
        challenge_token = webauthn.get("challenge_token")
        if not isinstance(credential, dict) or not isinstance(challenge_token, str):
            raise serializers.ValidationError("定位上报必须携带本人验证结果")
        webauthn_credential = verify_location_challenge(
            user=request.user,
            challenge_token=challenge_token,
            credential=credential,
            payload_hash=location_payload_hash(serializer.validated_data),
            request=request,
        )
        report = serializer.save()
        audit_log(
            user=request.user,
            action="location.report",
            resource=report,
            result="success",
            request=request,
            after_data={
                "report_status": report.report_status,
                "webauthn_credential_id": webauthn_credential.id,
            },
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
