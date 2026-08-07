import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from .models import LocationReport
from .services import LocationSnapshot


class LocationReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationReport
        fields = [
            "id",
            "longitude",
            "latitude",
            "accuracy",
            "address",
            "report_status",
            "failure_reason",
            "reported_at",
            "created_at",
        ]
        read_only_fields = ["id", "reported_at", "created_at"]


class LocationWebAuthnChallengeResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    token = serializers.CharField()
    options = serializers.DictField()


class LocationChallengeNotRequiredResponseSerializer(serializers.Serializer):
    status = serializers.CharField()


class LocationReportRequestSerializer(serializers.ModelSerializer):
    longitude = serializers.FloatField(required=False, allow_null=True)
    latitude = serializers.FloatField(required=False, allow_null=True)
    accuracy = serializers.FloatField(required=False, allow_null=True)
    webauthn = serializers.DictField(write_only=True, required=True)
    report_status = serializers.ChoiceField(
        choices=LocationReport.ReportStatus.choices,
        default=LocationReport.ReportStatus.SUCCESS,
    )

    class Meta:
        model = LocationReport
        fields = [
            "longitude",
            "latitude",
            "accuracy",
            "address",
            "report_status",
            "failure_reason",
            "webauthn",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["webauthn"].required = bool(self.context.get("require_webauthn", True))

    def validate_longitude(self, value):
        if value is not None and not (Decimal("-180") <= Decimal(str(value)) <= Decimal("180")):
            raise serializers.ValidationError("经度必须在 -180 到 180 之间")
        return value

    def validate_latitude(self, value):
        if value is not None and not (Decimal("-90") <= Decimal(str(value)) <= Decimal("90")):
            raise serializers.ValidationError("纬度必须在 -90 到 90 之间")
        return value

    def validate_accuracy(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("定位精度不能小于 0")
        return value

    def validate(self, attrs):
        report_status = attrs.get("report_status", LocationReport.ReportStatus.SUCCESS)
        longitude = attrs.get("longitude")
        latitude = attrs.get("latitude")

        if report_status == LocationReport.ReportStatus.SUCCESS and (
            longitude is None or latitude is None
        ):
            raise serializers.ValidationError("定位成功时必须提交经度和纬度")

        if report_status == LocationReport.ReportStatus.SUCCESS:
            attrs["longitude"] = quantize_decimal(longitude, "0.000001")
            attrs["latitude"] = quantize_decimal(latitude, "0.000001")
            if attrs.get("accuracy") is not None:
                attrs["accuracy"] = quantize_decimal(attrs["accuracy"], "0.01")

        if report_status == LocationReport.ReportStatus.LOCATE_FAILED:
            attrs["longitude"] = None
            attrs["latitude"] = None
            attrs["accuracy"] = None
            attrs.setdefault("failure_reason", "浏览器定位失败")

        return attrs

    def create(self, validated_data):
        validated_data.pop("webauthn", None)
        return LocationReport.objects.create(
            user=self.context["request"].user,
            reported_at=timezone.now(),
            **validated_data,
        )


def quantize_decimal(value: float, precision: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(precision), rounding=ROUND_HALF_UP)


def location_payload_hash(validated_data: dict[str, Any]) -> str:
    payload = {
        "longitude": normalize_payload_value(validated_data.get("longitude")),
        "latitude": normalize_payload_value(validated_data.get("latitude")),
        "accuracy": normalize_payload_value(validated_data.get("accuracy")),
        "address": validated_data.get("address", ""),
        "report_status": validated_data.get(
            "report_status",
            LocationReport.ReportStatus.SUCCESS,
        ),
        "failure_reason": validated_data.get("failure_reason", ""),
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def normalize_payload_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


class LocationUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    real_name = serializers.CharField()
    employee_no = serializers.CharField(allow_blank=True, allow_null=True)
    role = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)


class LocationSnapshotSerializer(serializers.Serializer):
    user = LocationUserSerializer()
    latest_report = LocationReportSerializer(allow_null=True)
    location_status = serializers.CharField()
    should_report = serializers.BooleanField()

    def to_representation(self, instance: LocationSnapshot) -> dict[str, Any]:
        latest_report = instance.latest_report
        latest_report_data = LocationReportSerializer(latest_report).data if latest_report else None
        return {
            "user": LocationUserSerializer(instance.user).data,
            "latest_report": latest_report_data,
            "location_status": instance.location_status,
            "should_report": instance.should_report,
        }
