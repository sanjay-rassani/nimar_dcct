from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from metrics.services import (
    dashboard_payload,
    issue_metrics,
    module_metrics,
    overview_metrics,
    phase_metrics,
    trend_metrics,
)
from tracker.permissions import can_view_points


@login_required
@require_GET
def api_metrics_overview(request: HttpRequest) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    return JsonResponse(overview_metrics())


@login_required
@require_GET
def api_metrics_phases(request: HttpRequest) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    return JsonResponse({"results": phase_metrics()})


@login_required
@require_GET
def api_metrics_modules(request: HttpRequest) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    return JsonResponse({"results": module_metrics()})


@login_required
@require_GET
def api_metrics_issues(request: HttpRequest) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    return JsonResponse(issue_metrics())


@login_required
@require_GET
def api_metrics_trends(request: HttpRequest) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    days = int(request.GET.get("days") or 30)
    return JsonResponse(trend_metrics(days=min(max(days, 7), 90)))


@login_required
@require_GET
def api_dashboard(request: HttpRequest) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    return JsonResponse(dashboard_payload(actor=request.user))
