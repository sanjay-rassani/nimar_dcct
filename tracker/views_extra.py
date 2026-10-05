from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from metrics.services import phase_metrics
from tracker.models import IssueStatus, Point, PointStatus
from tracker.permissions import can_view_points
from tracker.workflow import allowed_next_statuses


@login_required
def kanban_view(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "tracker/kanban.html",
        {
            "statuses": PointStatus.choices,
            "is_forbmax": request.user.is_forbmax,
            "is_nimar": request.user.is_nimar,
        },
    )


@login_required
def timeline_view(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "tracker/timeline.html",
        {"is_forbmax": request.user.is_forbmax, "is_nimar": request.user.is_nimar},
    )


@login_required
@require_GET
def api_kanban(request: HttpRequest) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)

    qs = (
        Point.objects.select_related("module", "phase", "owner")
        .annotate(
            open_issue_count=Count(
                "issues",
                filter=~Q(issues__status=IssueStatus.CLOSED),
                distinct=True,
            )
        )
        .order_by("external_id")
    )
    columns = {
        value: {"status": value, "label": label, "cards": []}
        for value, label in PointStatus.choices
    }
    for point in qs:
        columns[point.status]["cards"].append(
            {
                "id": point.pk,
                "external_id": point.external_id,
                "module": point.module.name if point.module_id else None,
                "title": point.title or (point.requirement or "")[:80],
                "phase": point.phase.name if point.phase_id else None,
                "due_date": point.due_date.isoformat() if point.due_date else None,
                "open_issue_count": point.open_issue_count,
                "status": point.status,
                "allowed_next_statuses": [
                    {"value": s, "label": PointStatus(s).label}
                    for s in allowed_next_statuses(point.status)
                ],
            }
        )
    return JsonResponse({"columns": list(columns.values())})


@login_required
@require_GET
def api_timeline(request: HttpRequest) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    return JsonResponse({"phases": phase_metrics()})
