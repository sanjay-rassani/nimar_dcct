"""Role-based field access for Delivery Points."""

from accounts.models import User

# Fields NIMAR may write when client response is enabled
NIMAR_WRITABLE = {
    "nimar_response",
    "decision",
    "status",  # limited further in validate_nimar_status_change
}

# Operational fields Forbmax Member may write
MEMBER_WRITABLE = {
    "title",
    "requirement",
    "status",
    "forbmax_response",
    "nimar_response",
    "decision",
    "remarks",
    "owner_id",
    "due_date",
    "scope_approved",
    "notes",
    "module_id",
    "phase_id",
    "annexure",
    "number",
}

# Admin can write everything including identity / create keys
ADMIN_WRITABLE = MEMBER_WRITABLE | {
    "external_id",
    "organization_id",
    "source_metadata",
}

# Restricted internal fields NIMAR must never write
NIMAR_FORBIDDEN = {
    "external_id",
    "forbmax_response",
    "owner_id",
    "due_date",
    "scope_approved",
    "remarks",
    "module_id",
    "phase_id",
    "annexure",
    "number",
    "title",
    "requirement",
    "organization_id",
    "notes",
    "source_metadata",
}


def writable_fields_for(user: User) -> set[str]:
    if user.is_superuser or user.is_forbmax_admin:
        return set(ADMIN_WRITABLE)
    if user.role == User.Role.FORBMAX_MEMBER:
        return set(MEMBER_WRITABLE)
    if user.is_nimar:
        return set(NIMAR_WRITABLE)
    return set()


def can_create_point(user: User) -> bool:
    return user.is_superuser or user.is_forbmax


def can_view_points(user: User) -> bool:
    return user.is_authenticated and user.is_active


def filter_payload_for_role(user: User, payload: dict) -> dict:
    """Return only fields the user is allowed to write. Drops forbidden keys."""
    allowed = writable_fields_for(user)
    # Normalize owner/module/phase keys from API
    normalized = {}
    for key, value in payload.items():
        if key == "owner":
            key = "owner_id"
        elif key == "module":
            key = "module_id"
        elif key == "phase":
            key = "phase_id"
        elif key == "organization":
            key = "organization_id"
        if key in allowed:
            normalized[key] = value
    return normalized


def validate_nimar_status_change(user: User, point, new_status: str) -> None:
    """NIMAR may only request rework or close when awaiting verification."""
    from django.core.exceptions import ValidationError
    from tracker.models import PointStatus

    if not user.is_nimar:
        return
    if new_status == point.status:
        return
    allowed = {
        PointStatus.REWORK_REQUESTED,
        PointStatus.VERIFIED_CLOSED,
    }
    if point.status != PointStatus.AWAITING_VERIFICATION or new_status not in allowed:
        raise ValidationError(
            "NIMAR users can only set Rework Requested or Verified & Closed "
            "when a point is Awaiting Verification."
        )
