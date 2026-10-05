from audit.models import ActivityLog


def log_activity(
    *,
    actor,
    entity_type: str,
    entity_id: str,
    action: str,
    old_value=None,
    new_value=None,
    message: str = "",
    point_external_id: str | None = None,
):
    """Immutable audit entry. Optionally embed point id for cross-entity history."""
    org = getattr(actor, "organization", None) if actor else None
    if point_external_id and isinstance(new_value, dict):
        new_value = {**new_value, "point_external_id": point_external_id}
    elif point_external_id and new_value is None:
        new_value = {"point_external_id": point_external_id}

    ActivityLog.objects.create(
        actor=actor,
        organization=org,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        old_value=old_value,
        new_value=new_value,
        message=message,
    )


def point_history_logs(point):
    """Aggregate activity for a delivery point and its related records."""
    from django.db.models import Q

    from tracker.models import Attachment, Comment, Issue

    issue_ids = [str(i) for i in Issue.objects.filter(point=point).values_list("pk", flat=True)]
    comment_ids = [
        str(c)
        for c in Comment.objects.filter(Q(point=point) | Q(issue__point=point)).values_list("pk", flat=True)
    ]
    attachment_ids = [
        str(a)
        for a in Attachment.objects.filter(Q(point=point) | Q(issue__point=point)).values_list("pk", flat=True)
    ]

    return (
        ActivityLog.objects.filter(
            Q(entity_type="Point", entity_id=str(point.external_id))
            | Q(entity_type="Issue", entity_id__in=issue_ids)
            | Q(entity_type="Comment", entity_id__in=comment_ids)
            | Q(entity_type="Attachment", entity_id__in=attachment_ids)
        )
        .select_related("actor", "organization")
        .order_by("-created_at")
    )


def serialize_logs(logs, limit=100):
    rows = logs[:limit]
    return [
        {
            "id": log.pk,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "action": log.action,
            "actor": log.actor.name if log.actor_id else None,
            "organization": log.organization.code if log.organization_id else None,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "message": log.message,
            "created_at": log.created_at.isoformat(),
        }
        for log in rows
    ]
