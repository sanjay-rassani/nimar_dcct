from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.dateparse import parse_date

from audit.models import ActivityLog
from tracker.models import Module, Phase, Point, PointStatus
from tracker.permissions import filter_payload_for_role, validate_nimar_status_change
from tracker.workflow import validate_status_transition


TRACKED_FIELDS = [
    "external_id",
    "annexure",
    "number",
    "module_id",
    "phase_id",
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
]


def _serialize_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def snapshot_point(point: Point) -> dict:
    data = {}
    for field in TRACKED_FIELDS:
        data[field] = _serialize_value(getattr(point, field))
    return data


def log_point_activity(*, actor, point: Point, action: str, old_value, new_value, message: str = ""):
    ActivityLog.objects.create(
        actor=actor,
        organization=getattr(actor, "organization", None),
        entity_type="Point",
        entity_id=str(point.external_id),
        action=action,
        old_value=old_value,
        new_value=new_value,
        message=message,
    )


def _apply_fk(point: Point, field: str, value, model):
    if value in (None, ""):
        setattr(point, field, None)
        return
    try:
        setattr(point, field, model.objects.get(pk=int(value)))
    except (TypeError, ValueError, model.DoesNotExist) as exc:
        raise ValidationError({field: f"Invalid {field}."}) from exc


@transaction.atomic
def create_point(*, actor, payload: dict) -> Point:
    from tracker.permissions import can_create_point

    if not can_create_point(actor):
        raise ValidationError("You do not have permission to create points.")

    data = filter_payload_for_role(actor, payload)
    # Point ID is always required on create (even if not later editable by role)
    external_id = (payload.get("external_id") or data.get("external_id") or "").strip()
    if not external_id:
        raise ValidationError({"external_id": "Point ID is required."})
    if Point.objects.filter(external_id=external_id).exists():
        raise ValidationError({"external_id": "Point ID must be unique."})

    point = Point(external_id=external_id, updated_by=actor)
    if actor.organization_id:
        point.organization = actor.organization

    _apply_fields(point, data, actor, is_create=True)
    point.full_clean()
    point.save()
    log_point_activity(
        actor=actor,
        point=point,
        action="create",
        old_value=None,
        new_value=snapshot_point(point),
        message="Point created",
    )
    return point


@transaction.atomic
def update_point(*, actor, point: Point, payload: dict) -> Point:
    data = filter_payload_for_role(actor, payload)
    if not data:
        raise ValidationError("No permitted fields to update.")

    old = snapshot_point(point)
    _apply_fields(point, data, actor, is_create=False)
    point.updated_by = actor
    point.full_clean()
    point.save()
    new = snapshot_point(point)

    changed = {k: {"old": old[k], "new": new[k]} for k in TRACKED_FIELDS if old[k] != new[k]}
    if changed:
        action = "status_change" if "status" in changed and len(changed) == 1 else "update"
        if "status" in changed and len(changed) > 1:
            action = "update"
        elif "status" in changed:
            action = "status_change"
        if "owner_id" in changed:
            action = "owner_change" if len(changed) == 1 else action
        if "decision" in changed and action == "update":
            action = "decision_change" if len(changed) == 1 else action
        log_point_activity(
            actor=actor,
            point=point,
            action=action,
            old_value={k: v["old"] for k, v in changed.items()},
            new_value={k: v["new"] for k, v in changed.items()},
            message=f"Updated: {', '.join(changed.keys())}",
        )
    return point


def _apply_fields(point: Point, data: dict, actor, *, is_create: bool) -> None:
    pending_status = data.get("status", point.status)
    pending_scope = data.get("scope_approved", point.scope_approved)
    pending_nimar = data.get("nimar_response", point.nimar_response)
    pending_decision = data.get("decision", point.decision)

    # Apply non-status fields first so transition checks see updated gates
    for key, value in data.items():
        if key == "status":
            continue
        if key == "due_date":
            if value in (None, ""):
                point.due_date = None
            else:
                parsed = parse_date(str(value)) if not hasattr(value, "year") else value
                if parsed is None:
                    raise ValidationError({"due_date": "Invalid date."})
                point.due_date = parsed
        elif key == "owner_id":
            from accounts.models import User

            if value in (None, ""):
                point.owner = None
            else:
                try:
                    point.owner = User.objects.get(pk=int(value))
                except (TypeError, ValueError, User.DoesNotExist) as exc:
                    raise ValidationError({"owner_id": "Invalid owner."}) from exc
        elif key == "module_id":
            _apply_fk(point, "module", value, Module)
        elif key == "phase_id":
            _apply_fk(point, "phase", value, Phase)
        elif key == "scope_approved":
            point.scope_approved = bool(value)
        elif key in {
            "external_id",
            "annexure",
            "number",
            "title",
            "requirement",
            "forbmax_response",
            "nimar_response",
            "decision",
            "remarks",
            "notes",
        }:
            setattr(point, key, value if value is not None else "")
        elif key == "source_metadata" and isinstance(value, dict):
            point.source_metadata = value

    # Re-read pending gates after assigns
    if "scope_approved" in data:
        pending_scope = point.scope_approved
    if "nimar_response" in data:
        pending_nimar = point.nimar_response
    if "decision" in data:
        pending_decision = point.decision

    if "status" in data:
        new_status = data["status"]
        if new_status not in PointStatus.values:
            raise ValidationError({"status": f"Unsupported status: {new_status}."})

        # Temporary point state for validation
        original_scope = point.scope_approved
        original_nimar = point.nimar_response
        original_decision = point.decision
        point.scope_approved = pending_scope
        point.nimar_response = pending_nimar or ""
        point.decision = pending_decision or ""

        validate_nimar_status_change(actor, point, new_status)
        # For IN_PROGRESS gate, use pending scope
        try:
            validate_status_transition(point, new_status)
        except ValidationError:
            point.scope_approved = original_scope
            point.nimar_response = original_nimar
            point.decision = original_decision
            raise

        point.status = new_status
        point.scope_approved = pending_scope
        point.nimar_response = pending_nimar or ""
        point.decision = pending_decision or ""
