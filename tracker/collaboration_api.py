import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods

from accounts.models import User
from tracker.activity_log import point_history_logs, serialize_logs
from tracker.collaboration import (
    attachment_dict,
    create_attachment,
    create_comment,
    create_issue,
    issue_detail_dict,
    update_issue,
)
from tracker.models import Attachment, Issue, IssueStatus, Point
from tracker.permissions import can_view_points


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


@login_required
@require_http_methods(["GET", "POST"])
def api_issues_list(request: HttpRequest) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)

    if request.method == "POST":
        try:
            payload = _json_body(request)
            point_id = payload.get("point_id") or request.GET.get("point")
            if not point_id:
                return JsonResponse({"detail": "point_id is required."}, status=400)
            point = get_object_or_404(Point, pk=point_id)
            issue = create_issue(actor=request.user, point=point, payload=payload)
            return JsonResponse(issue_detail_dict(issue, actor=request.user), status=201)
        except ValidationError as exc:
            return _error_response(exc)

    qs = Issue.objects.select_related(
        "point", "raised_by", "assigned_to", "resolved_by"
    ).order_by("-created_at")

    if point := request.GET.get("point"):
        qs = qs.filter(point_id=point)
    if status := request.GET.get("status"):
        qs = qs.filter(status=status)

    paginator = Paginator(qs, min(int(request.GET.get("page_size") or 25), 100))
    page = paginator.get_page(request.GET.get("page") or 1)
    return JsonResponse(
        {
            "count": paginator.count,
            "page": page.number,
            "num_pages": paginator.num_pages,
            "results": [issue_detail_dict(i, actor=request.user) for i in page.object_list],
        }
    )


@login_required
@require_http_methods(["GET", "PATCH"])
def api_issue_detail(request: HttpRequest, issue_id: int) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)

    issue = get_object_or_404(
        Issue.objects.select_related("point", "raised_by", "assigned_to", "resolved_by"),
        pk=issue_id,
    )

    if request.method == "GET":
        return JsonResponse(issue_detail_dict(issue, actor=request.user))

    try:
        issue = update_issue(actor=request.user, issue=issue, payload=_json_body(request))
        issue = Issue.objects.select_related(
            "point", "raised_by", "assigned_to", "resolved_by"
        ).get(pk=issue.pk)
        return JsonResponse(issue_detail_dict(issue, actor=request.user))
    except ValidationError as exc:
        return _error_response(exc)


@login_required
@require_http_methods(["POST"])
def api_point_comments(request: HttpRequest, point_id: int) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    point = get_object_or_404(Point, pk=point_id)
    try:
        payload = _json_body(request)
        comment = create_comment(
            actor=request.user,
            point=point,
            issue=None,
            message=payload.get("message", ""),
        )
        return JsonResponse(
            {
                "id": comment.pk,
                "author": comment.author.name,
                "message": comment.message,
                "created_at": comment.created_at.isoformat(),
            },
            status=201,
        )
    except ValidationError as exc:
        return _error_response(exc)


@login_required
@require_http_methods(["POST"])
def api_issue_comments(request: HttpRequest, issue_id: int) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    issue = get_object_or_404(Issue, pk=issue_id)
    try:
        payload = _json_body(request)
        comment = create_comment(
            actor=request.user,
            point=None,
            issue=issue,
            message=payload.get("message", ""),
        )
        return JsonResponse(
            {
                "id": comment.pk,
                "author": comment.author.name,
                "message": comment.message,
                "created_at": comment.created_at.isoformat(),
            },
            status=201,
        )
    except ValidationError as exc:
        return _error_response(exc)


@login_required
@require_GET
def api_point_history(request: HttpRequest, point_id: int) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    point = get_object_or_404(Point, pk=point_id)
    logs = point_history_logs(point)
    return JsonResponse({"results": serialize_logs(logs)})


@login_required
@require_http_methods(["GET", "POST"])
def api_point_attachments(request: HttpRequest, point_id: int) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    point = get_object_or_404(Point, pk=point_id)

    if request.method == "GET":
        rows = Attachment.objects.filter(Q(point=point) | Q(issue__point=point)).select_related(
            "uploaded_by"
        )
        return JsonResponse({"results": [attachment_dict(a) for a in rows]})

    try:
        if request.content_type and "multipart/form-data" in request.content_type:
            att = create_attachment(
                actor=request.user,
                point=point,
                issue=None,
                label=request.POST.get("label", ""),
                attachment_type=request.POST.get("attachment_type", Attachment.AttachmentType.OTHER),
                url=request.POST.get("url", ""),
                file=request.FILES.get("file"),
            )
        else:
            payload = _json_body(request)
            att = create_attachment(
                actor=request.user,
                point=point,
                issue=None,
                label=payload.get("label", ""),
                attachment_type=payload.get("attachment_type", Attachment.AttachmentType.OTHER),
                url=payload.get("url", ""),
                file=None,
            )
        return JsonResponse(attachment_dict(att), status=201)
    except ValidationError as exc:
        return _error_response(exc)


@login_required
@require_http_methods(["POST"])
def api_issue_attachments(request: HttpRequest, issue_id: int) -> JsonResponse:
    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)
    issue = get_object_or_404(Issue, pk=issue_id)
    try:
        if request.content_type and "multipart/form-data" in request.content_type:
            att = create_attachment(
                actor=request.user,
                point=None,
                issue=issue,
                label=request.POST.get("label", ""),
                attachment_type=request.POST.get("attachment_type", Attachment.AttachmentType.VERIFICATION),
                url=request.POST.get("url", ""),
                file=request.FILES.get("file"),
            )
        else:
            payload = _json_body(request)
            att = create_attachment(
                actor=request.user,
                point=None,
                issue=issue,
                label=payload.get("label", ""),
                attachment_type=payload.get("attachment_type", Attachment.AttachmentType.VERIFICATION),
                url=payload.get("url", ""),
                file=None,
            )
        return JsonResponse(attachment_dict(att), status=201)
    except ValidationError as exc:
        return _error_response(exc)


@login_required
@require_GET
def api_register_summary(request: HttpRequest) -> JsonResponse:
    """Role-aware KPI strip for the register page."""
    from django.utils import timezone

    from tracker.models import PointStatus

    if not can_view_points(request.user):
        return JsonResponse({"detail": "Forbidden."}, status=403)

    today = timezone.localdate()
    points = Point.objects.all()
    open_issues = Issue.objects.exclude(status=IssueStatus.CLOSED).count()

    base = {
        "total_points": points.count(),
        "closed_points": points.filter(status=PointStatus.VERIFIED_CLOSED).count(),
        "open_issues": open_issues,
        "awaiting_verification": points.filter(status=PointStatus.AWAITING_VERIFICATION).count(),
        "rework_requested": points.filter(status=PointStatus.REWORK_REQUESTED).count(),
        "overdue_points": points.filter(due_date__lt=today)
        .exclude(status=PointStatus.VERIFIED_CLOSED)
        .count(),
    }

    if request.user.is_nimar:
        return JsonResponse(
            {
                **base,
                "view": "nimar",
                "needs_nimar_review": base["awaiting_verification"],
                "open_issues_you_can_raise": open_issues,
            }
        )

    return JsonResponse(
        {
            **base,
            "view": "forbmax",
            "in_progress": points.filter(status=PointStatus.IN_PROGRESS).count(),
            "client_pending": base["awaiting_verification"] + base["rework_requested"],
        }
    )
