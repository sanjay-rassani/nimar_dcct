import io
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from accounts.models import User
from tracker.collaboration import create_issue, update_issue
from tracker.models import IssueStatus, Point


@pytest.mark.django_db
def test_login_binds_org_role(client, seeded_data):
    resp = client.post(
        "/api/auth/login/",
        data=json.dumps({"email": "admin@forbmax.local", "password": "AdminPass123!"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "FORBMAX_ADMIN"
    assert body["organization"] == "FORBMAX"


@pytest.mark.django_db
def test_point_patch_and_nimar_forbidden_fields(admin_client, nimar_client, seeded_data):
    point = Point.objects.first()
    resp = admin_client.patch(
        f"/api/points/{point.pk}/",
        data=json.dumps({"forbmax_response": "Updated by admin"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["forbmax_response"] == "Updated by admin"

    resp = nimar_client.patch(
        f"/api/points/{point.pk}/",
        data=json.dumps({"forbmax_response": "hack"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_issue_lifecycle_permissions(seeded_data):
    nimar = User.objects.get(email="user@nimar.local")
    member = User.objects.get(email="member@forbmax.local")
    point = Point.objects.first()
    issue = create_issue(actor=nimar, point=point, payload={"title": "Gap", "description": "x"})
    issue = update_issue(actor=member, issue=issue, payload={"status": IssueStatus.ACKNOWLEDGED})
    issue = update_issue(actor=member, issue=issue, payload={"status": IssueStatus.IN_PROGRESS})
    issue = update_issue(actor=member, issue=issue, payload={"status": IssueStatus.RESOLVED})
    assert issue.resolved_at is not None
    issue = update_issue(actor=nimar, issue=issue, payload={"status": IssueStatus.CLOSED})
    assert issue.status == IssueStatus.CLOSED


@pytest.mark.django_db
def test_import_export_roundtrip(admin_client, seeded_data):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Point ID", "Module", "Requirement", "Status", "Phase"])
    ws.append(["E-900", "Reporting", "Export test point", "Planned", "Demo Day"])
    buf = io.BytesIO()
    wb.save(buf)
    upload = SimpleUploadedFile(
        "t.xlsx",
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp = admin_client.post("/api/import/excel/", {"file": upload})
    assert resp.status_code == 201
    job_id = resp.json()["id"]
    resp = admin_client.post(
        f"/api/import/{job_id}/sheet/",
        data=json.dumps({"sheet_name": "Sheet1"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    job = resp.json()
    resp = admin_client.post(
        f"/api/import/{job_id}/preview/",
        data=json.dumps(
            {
                "column_mapping": job["column_mapping"],
                "status_mapping": job["status_mapping"],
                "phase_mapping": job["phase_mapping"],
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["preview_summary"]["counts"]["FAIL"] == 0
    resp = admin_client.post(
        f"/api/import/{job_id}/confirm/",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert Point.objects.filter(external_id="E-900").exists()

    resp = admin_client.get("/api/export/excel/?q=E-900")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp["Content-Type"]


@pytest.mark.django_db
def test_import_annexure_style_without_point_id(admin_client, seeded_data):
    """Real NIMAR sheets: title row, S.No./Module-RFP/Current Status, IDs as A-{S.No.}."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Annex A"
    ws.append(["Annex-A"])
    ws.append(
        [
            "S.No.",
            "Module-RFP",
            "To Do's",
            "Current Status",
            "Forbmax Response",
            "Remarks",
            "QA Remarks",
        ]
    )
    ws.append(
        [
            1,
            "Super Admin\nRFP Points: 1,2,3",
            "Audit trail visibility",
            "Not implemented",
            "Additional Requirement",
            "Demo Day",
            "needs retest",
        ]
    )
    buf = io.BytesIO()
    wb.save(buf)
    upload = SimpleUploadedFile(
        "Annexures Final.xlsx",
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp = admin_client.post("/api/import/excel/", {"file": upload})
    assert resp.status_code == 201
    job_id = resp.json()["id"]
    sheet = resp.json()["analysis"]["sheets"][0]
    assert sheet["header_row"] == 2
    assert "S.No." in sheet["headers"]

    resp = admin_client.post(
        f"/api/import/{job_id}/sheet/",
        data=json.dumps({"sheet_name": "Annex A"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    job = resp.json()
    assert job["column_mapping"].get("number") == "S.No."
    assert job["column_mapping"].get("status") == "Current Status"
    assert job["column_mapping"].get("phase") == "Remarks"
    assert job["phase_mapping"].get("Demo Day") == "DEMO_DAY"
    # Free-form status stays unmapped until user maps it
    assert "Not implemented" not in (job["status_mapping"] or {})

    status_mapping = {"Not implemented": "PLANNED"}
    resp = admin_client.post(
        f"/api/import/{job_id}/preview/",
        data=json.dumps(
            {
                "column_mapping": job["column_mapping"],
                "status_mapping": status_mapping,
                "phase_mapping": job["phase_mapping"],
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 200
    preview = resp.json()["preview_summary"]
    assert preview["counts"]["FAIL"] == 0
    assert preview["counts"]["CREATE"] == 1
    row = preview["rows"][0]
    assert row["external_id"] == "A-1"
    assert row["values"]["module"] == "Super Admin"
    assert row["values"]["phase"] == "DEMO_DAY"
    assert row["values"]["nimar_response"] == "needs retest"

    resp = admin_client.post(
        f"/api/import/{job_id}/confirm/",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    point = Point.objects.get(external_id="A-1")
    assert point.module.name == "Super Admin"
    assert point.phase.code == "DEMO_DAY"


@pytest.mark.django_db
def test_permission_matrix(admin_client, member_client, nimar_client, seeded_data):
    # Admin can open users page API
    assert admin_client.get("/api/users/").status_code == 200
    # Member cannot manage users
    assert member_client.get("/api/users/").status_code == 403
    # NIMAR cannot import
    assert nimar_client.get("/api/import/").status_code == 403
    # NIMAR can view metrics
    assert nimar_client.get("/api/metrics/overview/").status_code == 200
    # NIMAR cannot see Users nav target page (403)
    assert nimar_client.get("/users/").status_code == 403


@pytest.mark.django_db
def test_dashboard_and_kanban(admin_client, nimar_client, seeded_data):
    r = admin_client.get("/api/dashboard/")
    assert r.status_code == 200
    assert r.json()["view"] == "forbmax"
    r = nimar_client.get("/api/dashboard/")
    assert r.status_code == 200
    assert r.json()["view"] == "nimar"
    r = admin_client.get("/api/kanban/")
    assert r.status_code == 200
    assert len(r.json()["columns"]) == 6
    r = admin_client.get("/api/timeline/")
    assert r.status_code == 200
    assert len(r.json()["phases"]) == 4
