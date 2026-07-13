from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.db.models import OuterRef, Subquery
from django.db.models.query import QuerySet
from django.utils import timezone

from apps.accounts.models import User

from .models import LocationReport

LOCATION_FRESHNESS_HOURS = 4


class LocationState:
    NORMAL = "normal"
    EXPIRED = "expired"
    TODAY_UNREPORTED = "today_unreported"
    LOCATE_FAILED = "locate_failed"


@dataclass(frozen=True)
class LocationSnapshot:
    user: Any
    latest_report: LocationReport | None
    location_status: str
    should_report: bool


def get_latest_report(user: User) -> LocationReport | None:
    return LocationReport.objects.filter(user=user).order_by("-reported_at", "-id").first()


def get_active_employee_users() -> QuerySet[User]:
    return (
        User.objects.filter(is_active=True)
        .exclude(role=User.Role.TEMPORARY_USER)
        .order_by("-is_active", "id")
    )


def get_admin_location_snapshots() -> list[LocationSnapshot]:
    latest_report_id = (
        LocationReport.objects.filter(user=OuterRef("pk"))
        .order_by("-reported_at", "-id")
        .values("id")[:1]
    )
    users = list(
        get_active_employee_users().annotate(latest_location_report_id=Subquery(latest_report_id))
    )
    report_ids = [
        user.latest_location_report_id for user in users if user.latest_location_report_id
    ]
    reports = {
        report.id: report
        for report in LocationReport.objects.filter(id__in=report_ids).select_related("user")
    }
    now = timezone.now()
    return [
        build_location_snapshot(
            user=user,
            latest_report=reports.get(user.latest_location_report_id),
            now=now,
        )
        for user in users
    ]


def build_location_snapshot(
    *,
    user: Any,
    latest_report: LocationReport | None,
    now: datetime | None = None,
) -> LocationSnapshot:
    now = now or timezone.now()
    status = resolve_location_status(latest_report=latest_report, now=now)
    return LocationSnapshot(
        user=user,
        latest_report=latest_report,
        location_status=status,
        should_report=status != LocationState.NORMAL,
    )


def resolve_location_status(
    *, latest_report: LocationReport | None, now: datetime | None = None
) -> str:
    if latest_report is None:
        return LocationState.TODAY_UNREPORTED

    now = now or timezone.now()
    if latest_report.report_status == LocationReport.ReportStatus.LOCATE_FAILED:
        return LocationState.LOCATE_FAILED

    if timezone.localdate(latest_report.reported_at) != timezone.localdate(now):
        return LocationState.TODAY_UNREPORTED

    if latest_report.reported_at < now - timedelta(hours=LOCATION_FRESHNESS_HOURS):
        return LocationState.EXPIRED

    return LocationState.NORMAL
