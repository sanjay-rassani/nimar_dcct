"""
Lightweight metrics calculated from relational Point/Issue data.
"""
from __future__ import annotations

from datetime import timedelta
from statistics import median

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from tracker.models import Issue, IssueStatus, Module, Phase, Point, PointStatus


def _completion_pct(closed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((closed / total) * 100, 1)


def overview_metrics() -> dict:
    today = timezone.localdate()
    points = Point.objects.all()
    total = points.count()
    closed = points.filter(status=PointStatus.VERIFIED_CLOSED).count()
    open_points = total - closed
    in_progress = points.filter(status=PointStatus.IN_PROGRESS).count()
    awaiting = points.filter(status=PointStatus.AWAITING_VERIFICATION).count()
    rework = points.filter(status=PointStatus.REWORK_REQUESTED).count()
    overdue = (
        points.filter(due_date__lt=today)
        .exclude(status=PointStatus.VERIFIED_CLOSED)
        .count()
    )
    open_issues = Issue.objects.exclude(status=IssueStatus.CLOSED).count()
    resolved_issues = Issue.objects.filter(
        status__in=[IssueStatus.RESOLVED, IssueStatus.CLOSED]
    ).count()

    waiting_nimar = awaiting
    waiting_forbmax = points.filter(
        status__in=[
            PointStatus.PLANNED,
            PointStatus.SCOPE_APPROVAL,
            PointStatus.IN_PROGRESS,
            PointStatus.REWORK_REQUESTED,
        ]
    ).count()

    return {
        "total": total,
        "closed": closed,
        "open": open_points,
        "in_progress": in_progress,
        "awaiting_verification": awaiting,
        "rework_requested": rework,
        "overdue": overdue,
        "open_issues": open_issues,
        "resolved_issues": resolved_issues,
        "completion_pct": _completion_pct(closed, total),
        "waiting_for_forbmax": waiting_forbmax,
        "waiting_for_nimar": waiting_nimar,
        "client_pending": awaiting + rework,
    }


def phase_metrics() -> list[dict]:
    rows = []
    for phase in Phase.objects.filter(is_active=True).order_by("sort_order"):
        qs = Point.objects.filter(phase=phase)
        total = qs.count()
        closed = qs.filter(status=PointStatus.VERIFIED_CLOSED).count()
        rows.append(
            {
                "id": phase.pk,
                "code": phase.code,
                "name": phase.name,
                "start_date": phase.start_date.isoformat() if phase.start_date else None,
                "end_date": phase.end_date.isoformat() if phase.end_date else None,
                "total": total,
                "planned": qs.filter(status=PointStatus.PLANNED).count(),
                "scope_approval": qs.filter(status=PointStatus.SCOPE_APPROVAL).count(),
                "in_progress": qs.filter(status=PointStatus.IN_PROGRESS).count(),
                "awaiting_verification": qs.filter(
                    status=PointStatus.AWAITING_VERIFICATION
                ).count(),
                "rework": qs.filter(status=PointStatus.REWORK_REQUESTED).count(),
                "closed": closed,
                "open": total - closed,
                "issues": Issue.objects.filter(point__phase=phase)
                .exclude(status=IssueStatus.CLOSED)
                .count(),
                "overdue": qs.filter(due_date__lt=timezone.localdate())
                .exclude(status=PointStatus.VERIFIED_CLOSED)
                .count(),
                "completion_pct": _completion_pct(closed, total),
            }
        )
    return rows


def module_metrics() -> list[dict]:
    rows = []
    for module in Module.objects.filter(is_active=True).order_by("name"):
        qs = Point.objects.filter(module=module)
        total = qs.count()
        closed = qs.filter(status=PointStatus.VERIFIED_CLOSED).count()
        rows.append(
            {
                "id": module.pk,
                "name": module.name,
                "total": total,
                "completed": closed,
                "open": total - closed,
                "issues": Issue.objects.filter(point__module=module)
                .exclude(status=IssueStatus.CLOSED)
                .count(),
                "completion_pct": _completion_pct(closed, total),
            }
        )
    # Points with no module
    none_qs = Point.objects.filter(module__isnull=True)
    if none_qs.exists():
        total = none_qs.count()
        closed = none_qs.filter(status=PointStatus.VERIFIED_CLOSED).count()
        rows.append(
            {
                "id": None,
                "name": "(No module)",
                "total": total,
                "completed": closed,
                "open": total - closed,
                "issues": Issue.objects.filter(point__module__isnull=True)
                .exclude(status=IssueStatus.CLOSED)
                .count(),
                "completion_pct": _completion_pct(closed, total),
            }
        )
    return rows


def issue_metrics() -> dict:
    open_qs = Issue.objects.exclude(status=IssueStatus.CLOSED)
    by_status = {
        value: Issue.objects.filter(status=value).count() for value, _ in IssueStatus.choices
    }
    resolved = Issue.objects.exclude(resolved_at__isnull=True)
    durations = []
    for issue in resolved.only("created_at", "resolved_at"):
        if issue.resolved_at and issue.created_at:
            durations.append((issue.resolved_at - issue.created_at).total_seconds() / 3600.0)

    oldest = open_qs.order_by("created_at").select_related("point").first()

    # NIMAR response time: Awaiting Verification activity → nimar_response/decision change
    # Approximate using points currently/formerly awaiting with nimar_response set and updated_at
    nimar_times = []
    for point in Point.objects.exclude(nimar_response="").only("created_at", "updated_at", "nimar_response"):
        if point.updated_at and point.created_at:
            nimar_times.append((point.updated_at - point.created_at).total_seconds() / 3600.0)

    return {
        "open_issues": open_qs.count(),
        "resolved_issues": Issue.objects.filter(
            status__in=[IssueStatus.RESOLVED, IssueStatus.CLOSED]
        ).count(),
        "by_status": by_status,
        "avg_resolution_hours": round(sum(durations) / len(durations), 1) if durations else None,
        "median_resolution_hours": round(median(durations), 1) if durations else None,
        "avg_nimar_response_hours": round(sum(nimar_times) / len(nimar_times), 1) if nimar_times else None,
        "oldest_open_issue": (
            {
                "id": oldest.pk,
                "title": oldest.title,
                "point_external_id": oldest.point.external_id,
                "created_at": oldest.created_at.isoformat(),
                "age_days": (timezone.now() - oldest.created_at).days,
            }
            if oldest
            else None
        ),
    }


def trend_metrics(days: int = 30) -> dict:
    start = timezone.now() - timedelta(days=days)
    closed_by_day = (
        Point.objects.filter(status=PointStatus.VERIFIED_CLOSED, updated_at__gte=start)
        .annotate(day=TruncDate("updated_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    issues_opened = (
        Issue.objects.filter(created_at__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    issues_resolved = (
        Issue.objects.filter(resolved_at__gte=start)
        .annotate(day=TruncDate("resolved_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    # Cumulative completion snapshot series (simple daily closed count + running total estimate)
    total = Point.objects.count()
    closed_total = Point.objects.filter(status=PointStatus.VERIFIED_CLOSED).count()
    closed_series = [
        {"date": row["day"].isoformat(), "count": row["count"]} for row in closed_by_day if row["day"]
    ]
    return {
        "days": days,
        "points_closed_over_time": closed_series,
        "issues_opened_over_time": [
            {"date": row["day"].isoformat(), "count": row["count"]}
            for row in issues_opened
            if row["day"]
        ],
        "issues_resolved_over_time": [
            {"date": row["day"].isoformat(), "count": row["count"]}
            for row in issues_resolved
            if row["day"]
        ],
        "completion_snapshot": {
            "total": total,
            "closed": closed_total,
            "completion_pct": _completion_pct(closed_total, total),
        },
    }


def dashboard_payload(*, actor) -> dict:
    overview = overview_metrics()
    phases = phase_metrics()
    modules = module_metrics()
    issues = issue_metrics()
    trends = trend_metrics()

    recent = (
        Point.objects.select_related("module", "phase", "updated_by")
        .order_by("-updated_at")[:8]
    )
    recent_updates = [
        {
            "id": p.pk,
            "external_id": p.external_id,
            "title": p.title or p.requirement[:80],
            "status": p.status,
            "status_label": PointStatus(p.status).label,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "updated_by": p.updated_by.name if p.updated_by_id else None,
        }
        for p in recent
    ]

    needs_nimar = list(
        Point.objects.filter(status=PointStatus.AWAITING_VERIFICATION)
        .select_related("module", "phase")
        .order_by("due_date", "external_id")[:12]
        .values("id", "external_id", "title", "requirement", "module__name", "due_date")
    )
    for row in needs_nimar:
        row["module"] = row.pop("module__name")
        row["due_date"] = row["due_date"].isoformat() if row["due_date"] else None
        row["title"] = row["title"] or (row["requirement"] or "")[:80]
        row.pop("requirement", None)

    payload = {
        "view": "nimar" if actor.is_nimar else "forbmax",
        "overview": overview,
        "phases": phases,
        "modules": modules,
        "issues": issues,
        "trends": trends,
        "recent_updates": recent_updates,
        "needs_nimar_review": needs_nimar,
    }
    if not actor.is_nimar:
        payload["forbmax_focus"] = {
            "remaining_work": overview["open"],
            "overdue": overview["overdue"],
            "rework": overview["rework_requested"],
            "client_pending": overview["client_pending"],
            "open_issues": overview["open_issues"],
            "in_progress": overview["in_progress"],
        }
    return payload
