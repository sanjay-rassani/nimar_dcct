from django.core.exceptions import ValidationError

from tracker.models import PointStatus

# Happy path + rework loop
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PointStatus.PLANNED: {
        PointStatus.SCOPE_APPROVAL,
        PointStatus.IN_PROGRESS,
    },
    PointStatus.SCOPE_APPROVAL: {
        PointStatus.IN_PROGRESS,
        PointStatus.PLANNED,
    },
    PointStatus.IN_PROGRESS: {
        PointStatus.AWAITING_VERIFICATION,
        PointStatus.SCOPE_APPROVAL,
    },
    PointStatus.AWAITING_VERIFICATION: {
        PointStatus.VERIFIED_CLOSED,
        PointStatus.REWORK_REQUESTED,
        PointStatus.IN_PROGRESS,
    },
    PointStatus.REWORK_REQUESTED: {
        PointStatus.IN_PROGRESS,
    },
    PointStatus.VERIFIED_CLOSED: set(),
}


def allowed_next_statuses(current: str) -> list[str]:
    return sorted(ALLOWED_TRANSITIONS.get(current, set()))


def validate_status_transition(point, new_status: str) -> None:
    """Enforce lifecycle and gate rules. Raises ValidationError with clear messages."""
    current = point.status
    if new_status == current:
        return

    if new_status not in PointStatus.values:
        raise ValidationError(f"Unsupported status value: {new_status}.")

    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise ValidationError(
            f"Cannot move from {PointStatus(current).label} to {PointStatus(new_status).label}."
        )

    # Scope approval gate before active implementation
    if new_status == PointStatus.IN_PROGRESS and not point.scope_approved:
        # Approving while leaving Scope Approval may set the flag in the same PATCH
        raise ValidationError(
            "This point cannot move to In Progress because scope approval is pending."
        )

    # Closed only after NIMAR verification/acceptance evidence
    if new_status == PointStatus.VERIFIED_CLOSED:
        nimar_ok = bool((point.nimar_response or "").strip() or (point.decision or "").strip())
        if not nimar_ok:
            raise ValidationError(
                "This point cannot be Verified & Closed until NIMAR verification or "
                "acceptance is recorded (NIMAR response or decision)."
            )
