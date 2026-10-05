from tracker.activity_log import point_history_logs, serialize_logs
from tracker.collaboration import attachment_dict, issue_detail_dict
from tracker.models import Attachment, Comment, Issue, IssueStatus, Point, PointStatus
from tracker.workflow import allowed_next_statuses


def point_list_item(point: Point) -> dict:
    open_issues = getattr(point, "open_issue_count", None)
    if open_issues is None:
        open_issues = point.issues.exclude(status=IssueStatus.CLOSED).count()
    return {
        "id": point.pk,
        "external_id": point.external_id,
        "module": point.module.name if point.module_id else None,
        "module_id": point.module_id,
        "title": point.title,
        "requirement": point.requirement,
        "phase": point.phase.name if point.phase_id else None,
        "phase_id": point.phase_id,
        "status": point.status,
        "status_label": PointStatus(point.status).label if point.status in PointStatus.values else point.status,
        "owner": point.owner.name if point.owner_id else None,
        "owner_id": point.owner_id,
        "due_date": point.due_date.isoformat() if point.due_date else None,
        "open_issue_count": open_issues,
        "updated_at": point.updated_at.isoformat() if point.updated_at else None,
        "annexure": point.annexure,
    }


def point_detail(point: Point, *, include_history: bool = False, actor=None) -> dict:
    data = point_list_item(point)
    data.update(
        {
            "forbmax_response": point.forbmax_response,
            "nimar_response": point.nimar_response,
            "decision": point.decision,
            "remarks": point.remarks,
            "notes": point.notes,
            "scope_approved": point.scope_approved,
            "number": point.number,
            "organization_id": point.organization_id,
            "allowed_next_statuses": [
                {"value": s, "label": PointStatus(s).label} for s in allowed_next_statuses(point.status)
            ],
            "updated_by": point.updated_by.name if point.updated_by_id else None,
        }
    )

    issues = point.issues.select_related("raised_by", "assigned_to", "resolved_by").order_by("-created_at")
    data["issues"] = [issue_detail_dict(i, actor=actor) for i in issues]
    data["open_issues"] = issues.exclude(status=IssueStatus.CLOSED).count()

    point_attachments = list(point.attachments.select_related("uploaded_by").all())
    issue_attachment_rows = Attachment.objects.filter(issue__point=point).select_related("uploaded_by")
    seen = {a.pk for a in point_attachments}
    for row in issue_attachment_rows:
        if row.pk not in seen:
            point_attachments.append(row)
    data["attachments"] = [attachment_dict(a) for a in point_attachments]

    data["comments"] = [
        {
            "id": c.pk,
            "author": c.author.name,
            "message": c.message,
            "created_at": c.created_at.isoformat(),
        }
        for c in Comment.objects.filter(point=point).select_related("author").order_by("created_at")
    ]

    if include_history:
        data["activity"] = serialize_logs(point_history_logs(point))
    return data
