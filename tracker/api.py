import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods

from accounts.models import User
from tracker.models import IssueStatus, Module, Phase, Point, PointStatus
from tracker.permissions import can_create_point, can_view_points, writable_fields_for
from tracker.serializers import point_detail, point_list_item
from tracker.services import create_point, update_point


def _json_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid JSON body.") from exc
    if not isinstance(data, dict):
        raise ValidationError("JSON body must be an object.")
    return data


def _error_response(exc: ValidationError, status: int = 400) -> JsonResponse:
    if hasattr(exc, "message_dict"):
        return JsonResponse({"detail": exc.message_dict}, status=status)
    if hasattr(exc, "messages"):
        return JsonResponse({"detail": list(exc.messages)}, status=status)
    return JsonResponse({"detail": str(exc)}, status=status)


def _points_queryset():
    return (
        Point.objects.select_related("module", "phase", "owner", "updated_by")
        .annotate(
            open_issue_count=Count(
                "issues",
                filter=~Q(issues__status=IssueStatus.CLOSED),
                distinct=True,
            )
        )
    )


def _apply_filters(qs, params):
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(external_id__icontains=q)
            | Q(title__icontains=q)
            | Q(requirement__icontains=q)
            | Q(module__name__icontains=q)
            | Q(forbmax_response__icontains=q)
            | Q(nimar_response__icontains=q)
            | Q(decision__icontains=q)
            | Q(remarks__icontains=q)
            | Q(issues__title__icontains=q)
            | Q(issues__description__icontains=q)
        ).distinct()

    if phase := params.get("phase"):
        if phase.isdigit():
            qs = qs.filter(phase_id=int(phase))
        else:
            qs = qs.filter(phase__code=phase)

    if module := params.get("module"):
        if module.isdigit():
            qs = qs.filter(module_id=int(module))
        else:
            qs = qs.filter(module__name=module)

    if status := params.get("status"):
        qs = qs.filter(status=status)

    if annexure := params.get("annexure"):
        qs = qs.filter(annexure=annexure)

    if issue_status := params.get("issue_status"):
        qs = qs.filter(issues__status=issue_status).distinct()

    if owner := params.get("owner"):
        if owner.isdigit():
            qs = qs.filter(owner_id=int(owner))

    if due_from := params.get("due_from"):
        qs = qs.filter(due_date__gte=due_from)
    if due_to := params.get("due_to"):
        qs = qs.filter(due_date__lte=due_to)
    if updated_from := params.get("updated_from"):
        qs = qs.filter(updated_at__date__gte=updated_from)
    if updated_to := params.get("updated_to"):
        qs = qs.filter(updated_at__date__lte=updated_to)

    return qs


SORT_MAP = {
    "id": "external_id",
    "external_id": "external_id",
    "module": "module__name",
    "phase": "phase__sort_order",
    "status": "status",
    "due_date": "due_date",
    "updated_at": "updated_at",
}


def _apply_sort(qs, params):
    sort = params.get("sort") or "external_id"
    direction = params.get("dir") or "asc"
    field = SORT_MAP.get(sort, "external_id")
    if direction == "desc":
        field = f"-{field}"
    return qs.order_by(field, "external_id")


@login_required
@require_http_methods(["GET", "POST"])
def api_points_list(request: HttpRequest) -> JsonResponse:
    if request.method == "POST":
        if not can_create_point(request.user):
            return JsonResponse({"detail": "You do not have permission to create points."}, status=403)
        try:
            payload = _json_body(request)
            point = create_point(actor=request.user, payload=payload)
            point = _points_queryset().get(pk=point.pk)
            return JsonResponse(point_detail(point, include_history=True, actor=request.user), status=201)
        except ValidationError as exc:
            return _error_response(exc)

    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)

    qs = _apply_sort(_apply_filters(_points_queryset(), request.GET), request.GET)
    page_number = request.GET.get("page") or 1
    page_size = min(int(request.GET.get("page_size") or 25), 100)
    paginator = Paginator(qs, page_size)
    page = paginator.get_page(page_number)

    return JsonResponse(
        {
            "count": paginator.count,
            "page": page.number,
            "num_pages": paginator.num_pages,
            "page_size": page_size,
            "results": [point_list_item(p) for p in page.object_list],
            "writable_fields": sorted(writable_fields_for(request.user)),
            "can_create": can_create_point(request.user),
        }
    )


@login_required
@require_http_methods(["GET", "PATCH"])
def api_point_detail(request: HttpRequest, point_id: int) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)

    point = get_object_or_404(_points_queryset(), pk=point_id)

    if request.method == "GET":
        return JsonResponse(point_detail(point, include_history=True, actor=request.user))

    try:
        payload = _json_body(request)
        point = update_point(actor=request.user, point=point, payload=payload)
        point = _points_queryset().get(pk=point.pk)
        return JsonResponse(point_detail(point, include_history=True, actor=request.user))
    except ValidationError as exc:
        return _error_response(exc)


@login_required
@require_GET
def api_phases(request: HttpRequest) -> JsonResponse:
    rows = Phase.objects.filter(is_active=True).order_by("sort_order")
    return JsonResponse(
        {
            "results": [
                {
                    "id": p.pk,
                    "name": p.name,
                    "code": p.code,
                    "sort_order": p.sort_order,
                }
                for p in rows
            ]
        }
    )


@login_required
@require_GET
def api_modules(request: HttpRequest) -> JsonResponse:
    rows = Module.objects.filter(is_active=True).order_by("name")
    return JsonResponse({"results": [{"id": m.pk, "name": m.name} for m in rows]})


@login_required
@require_GET
def api_statuses(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "results": [{"value": value, "label": label} for value, label in PointStatus.choices]
        }
    )


@login_required
@require_GET
def api_owners(request: HttpRequest) -> JsonResponse:
    users = User.objects.filter(is_active=True, role__in=[User.Role.FORBMAX_ADMIN, User.Role.FORBMAX_MEMBER])
    return JsonResponse({"results": [{"id": u.pk, "name": u.name, "email": u.email} for u in users]})
