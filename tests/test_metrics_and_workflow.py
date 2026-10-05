import pytest
from django.core.exceptions import ValidationError

from metrics.services import _completion_pct, overview_metrics
from tracker.models import Point, PointStatus
from tracker.workflow import validate_status_transition


@pytest.mark.django_db
def test_completion_pct():
    assert _completion_pct(0, 0) == 0.0
    assert _completion_pct(1, 4) == 25.0
    assert _completion_pct(2, 3) == 66.7


@pytest.mark.django_db
def test_overview_matches_db(seeded_data):
    metrics = overview_metrics()
    total = Point.objects.count()
    closed = Point.objects.filter(status=PointStatus.VERIFIED_CLOSED).count()
    assert metrics["total"] == total
    assert metrics["closed"] == closed
    assert metrics["completion_pct"] == _completion_pct(closed, total)


@pytest.mark.django_db
def test_status_transition_requires_scope(seeded_data):
    point = Point.objects.filter(status=PointStatus.PLANNED).first()
    assert point is not None
    point.scope_approved = False
    with pytest.raises(ValidationError, match="scope approval"):
        validate_status_transition(point, PointStatus.IN_PROGRESS)


@pytest.mark.django_db
def test_closed_requires_nimar_verification(seeded_data):
    point = Point.objects.create(
        external_id="Z-TEST-1",
        status=PointStatus.AWAITING_VERIFICATION,
        scope_approved=True,
        nimar_response="",
        decision="",
    )
    with pytest.raises(ValidationError, match="NIMAR verification"):
        validate_status_transition(point, PointStatus.VERIFIED_CLOSED)
    point.decision = "Accepted"
    validate_status_transition(point, PointStatus.VERIFIED_CLOSED)
