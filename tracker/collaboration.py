import mimetypes
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from tracker.activity_log import log_activity
from tracker.issue_workflow import allowed_next_issue_statuses, validate_issue_transition
from tracker.models import Attachment, Comment, Issue, IssueStatus, Point
from tracker.permissions import can_view_points

EVIDENCE_ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".txt",
    ".doc",
    ".docx",
    ".xlsx",
    ".csv",
    ".mp4",
    ".webm",
}


def _require_point_access(actor, point: Point) -> None:
    if not can_view_points(actor):
        raise ValidationError("Forbidden.")


def _issue_snapshot(issue: Issue) -> dict:
    return {
        "id": issue.pk,
        "title": issue.title,
        "status": issue.status,
        "assigned_to_id": issue.assigned_to_id,
        "resolved_at": issue.resolved_at.isoformat() if issue.resolved_at else None,
        "resolved_by_id": issue.resolved_by_id,
    }


@transaction.atomic
def create_issue(*, actor, point: Point, payload: dict) -> Issue:
    _require_point_access(actor, point)
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValidationError({"title": "Issue title is required."})

    description = payload.get("description") or ""
    issue = Issue.objects.create(
        point=point,
        title=title,
        description=description,
        status=IssueStatus.OPEN,
        raised_by=actor,
    )

    log_activity(
        actor=actor,
        entity_type="Issue",
        entity_id=str(issue.pk),
        action="issue_create",
        new_value=_issue_snapshot(issue),
        message=f"Issue raised on {point.external_id}: {title}",
        point_external_id=point.external_id,
    )
    return issue


def _forbmax_can_manage_issue(actor) -> bool:
    return actor.is_superuser or actor.is_forbmax


@transaction.atomic
def update_issue(*, actor, issue: Issue, payload: dict) -> Issue:
    _require_point_access(actor, issue.point)
    old = _issue_snapshot(issue)

    if "title" in payload or "description" in payload:
        if not (_forbmax_can_manage_issue(actor) or issue.raised_by_id == actor.pk):
            raise ValidationError("You cannot edit this issue's title or description.")
        if "title" in payload:
            title = (payload.get("title") or "").strip()
            if not title:
                raise ValidationError({"title": "Issue title is required."})
            issue.title = title
        if "description" in payload:
            issue.description = payload.get("description") or ""

    if "assigned_to" in payload or "assigned_to_id" in payload:
        if not _forbmax_can_manage_issue(actor):
            raise ValidationError("Only Forbmax can assign issues.")
        assignee_raw = payload.get("assigned_to", payload.get("assigned_to_id"))
        if assignee_raw in (None, ""):
            issue.assigned_to = None
        else:
            try:
                assignee = User.objects.get(
                    pk=int(assignee_raw),
                    is_active=True,
                    role__in=[User.Role.FORBMAX_ADMIN, User.Role.FORBMAX_MEMBER],
                )
            except (TypeError, ValueError, User.DoesNotExist) as exc:
                raise ValidationError({"assigned_to": "Invalid assignee."}) from exc
            issue.assigned_to = assignee

    if "status" in payload:
        new_status = payload["status"]
        validate_issue_transition(actor=actor, issue=issue, new_status=new_status)
        issue.status = new_status
        if new_status == IssueStatus.RESOLVED:
            issue.resolved_at = timezone.now()
            issue.resolved_by = actor
        if new_status == IssueStatus.CLOSED and actor.is_nimar:
            # NIMAR verifies closure; resolver remains Forbmax from Resolved step
            pass

    if issue.status == IssueStatus.CLOSED:
        if not issue.resolved_at or not issue.resolved_by_id:
            raise ValidationError(
                "Closed issues require a resolver and resolution timestamp."
            )

    issue.save()
    new = _issue_snapshot(issue)
    changed = {k: {"old": old[k], "new": new[k]} for k in old if old[k] != new[k]}
    if changed:
        action = "issue_status_change" if "status" in changed and len(changed) == 1 else "issue_update"
        log_activity(
            actor=actor,
            entity_type="Issue",
            entity_id=str(issue.pk),
            action=action,
            old_value={k: v["old"] for k, v in changed.items()},
            new_value={k: v["new"] for k, v in changed.items()},
            message=f"Issue updated on {issue.point.external_id}",
            point_external_id=issue.point.external_id,
        )
    return issue


@transaction.atomic
def create_comment(*, actor, point: Point | None, issue: Issue | None, message: str) -> Comment:
    if not point and not issue:
        raise ValidationError("Comment must belong to a point or issue.")
    if issue:
        point = issue.point
    assert point is not None
    _require_point_access(actor, point)

    text = (message or "").strip()
    if not text:
        raise ValidationError({"message": "Comment message is required."})

    comment = Comment.objects.create(
        point=point if not issue else None,
        issue=issue,
        author=actor,
        message=text,
    )
    target = f"issue {issue.pk}" if issue else f"point {point.external_id}"
    log_activity(
        actor=actor,
        entity_type="Comment",
        entity_id=str(comment.pk),
        action="comment_create",
        new_value={"message": text, "target": target},
        message=f"Comment on {target}",
        point_external_id=point.external_id,
    )
    return comment


def validate_upload(file) -> None:
    max_bytes = getattr(settings, "EVIDENCE_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
    if file.size > max_bytes:
        raise ValidationError(
            f"File is too large. Maximum size is {max_bytes // (1024 * 1024)} MB."
        )
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in EVIDENCE_ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"File type '{ext or 'unknown'}' is not allowed for evidence uploads."
        )
    content_type = getattr(file, "content_type", "") or mimetypes.guess_type(file.name)[0] or ""
    if content_type.startswith("application/x-") or content_type == "application/octet-stream":
        # allow common docs with generic octet-stream from browsers
        if ext not in EVIDENCE_ALLOWED_EXTENSIONS:
            raise ValidationError("Unsupported file content type.")


@transaction.atomic
def create_attachment(
    *,
    actor,
    point: Point | None,
    issue: Issue | None,
    label: str,
    attachment_type: str,
    url: str = "",
    file=None,
) -> Attachment:
    if not point and not issue:
        raise ValidationError("Attachment must belong to a point or issue.")
    if issue:
        point = issue.point
    assert point is not None
    _require_point_access(actor, point)

    label = (label or "").strip()
    if not label:
        raise ValidationError({"label": "Label is required."})

    if not file and not (url or "").strip():
        raise ValidationError("Provide a file upload or URL.")

    if file:
        validate_upload(file)

    attachment = Attachment(
        point=point if not issue else None,
        issue=issue,
        label=label,
        url=(url or "").strip(),
        attachment_type=attachment_type or Attachment.AttachmentType.OTHER,
        uploaded_by=actor,
    )
    if file:
        attachment.file = file
    attachment.full_clean()
    attachment.save()

    log_activity(
        actor=actor,
        entity_type="Attachment",
        entity_id=str(attachment.pk),
        action="evidence_create",
        new_value={
            "label": label,
            "attachment_type": attachment.attachment_type,
            "url": attachment.url,
            "file": attachment.file.name if attachment.file else None,
        },
        message=f"Evidence added on {point.external_id}: {label}",
        point_external_id=point.external_id,
    )
    return attachment


def issue_detail_dict(issue: Issue, actor=None) -> dict:
    allowed = allowed_next_issue_statuses(issue.status)
    if actor and actor.is_nimar:
        allowed = [s for s in allowed if s == IssueStatus.CLOSED]
    elif actor and not (actor.is_forbmax or actor.is_superuser):
        allowed = []
    return {
        "id": issue.pk,
        "point_id": issue.point_id,
        "point_external_id": issue.point.external_id,
        "title": issue.title,
        "description": issue.description,
        "status": issue.status,
        "status_label": IssueStatus(issue.status).label,
        "raised_by": issue.raised_by.name if issue.raised_by_id else None,
        "raised_by_id": issue.raised_by_id,
        "assigned_to": issue.assigned_to.name if issue.assigned_to_id else None,
        "assigned_to_id": issue.assigned_to_id,
        "resolved_at": issue.resolved_at.isoformat() if issue.resolved_at else None,
        "resolved_by": issue.resolved_by.name if issue.resolved_by_id else None,
        "created_at": issue.created_at.isoformat(),
        "updated_at": issue.updated_at.isoformat(),
        "allowed_next_statuses": [
            {"value": s, "label": IssueStatus(s).label}
            for s in allowed
        ],
        "comments": [
            {
                "id": c.pk,
                "author": c.author.name,
                "message": c.message,
                "created_at": c.created_at.isoformat(),
            }
            for c in issue.comments.select_related("author").all()
        ],
        "attachments": [
            attachment_dict(a)
            for a in issue.attachments.select_related("uploaded_by").all()
        ],
    }


def attachment_dict(att: Attachment) -> dict:
    file_url = att.file.url if att.file else None
    return {
        "id": att.pk,
        "label": att.label,
        "attachment_type": att.attachment_type,
        "url": att.url or file_url,
        "file_url": file_url,
        "uploaded_by": att.uploaded_by.name if att.uploaded_by_id else None,
        "created_at": att.created_at.isoformat(),
        "issue_id": att.issue_id,
        "point_id": att.point_id,
    }
