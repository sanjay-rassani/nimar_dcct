from django.core.exceptions import ValidationError

from tracker.models import IssueStatus

ALLOWED_ISSUE_TRANSITIONS: dict[str, set[str]] = {
    IssueStatus.OPEN: {IssueStatus.ACKNOWLEDGED, IssueStatus.IN_PROGRESS},
    IssueStatus.ACKNOWLEDGED: {IssueStatus.IN_PROGRESS, IssueStatus.RESOLVED},
    IssueStatus.IN_PROGRESS: {IssueStatus.RESOLVED},
    IssueStatus.RESOLVED: {IssueStatus.CLOSED},
    IssueStatus.CLOSED: set(),
}


def allowed_next_issue_statuses(current: str) -> list[str]:
    return sorted(ALLOWED_ISSUE_TRANSITIONS.get(current, set()))


def validate_issue_transition(*, actor, issue, new_status: str) -> None:
    from accounts.models import User

    current = issue.status
    if new_status == current:
        return

    if new_status not in IssueStatus.values:
        raise ValidationError(f"Unsupported issue status: {new_status}.")

    allowed = ALLOWED_ISSUE_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise ValidationError(
            f"Cannot move issue from {IssueStatus(current).label} to {IssueStatus(new_status).label}."
        )

    if actor.is_nimar:
        if new_status != IssueStatus.CLOSED or current != IssueStatus.RESOLVED:
            raise ValidationError(
                "NIMAR users can only close an issue after Forbmax has marked it Resolved."
            )

    if actor.role == User.Role.FORBMAX_MEMBER or actor.is_forbmax_admin or actor.is_superuser:
        if new_status == IssueStatus.CLOSED and current != IssueStatus.RESOLVED:
            raise ValidationError("Issues must be Resolved before they can be Closed.")

    if new_status == IssueStatus.CLOSED:
        if not issue.resolved_at or not issue.resolved_by_id:
            raise ValidationError("Closed issues require a resolver and resolution timestamp.")
