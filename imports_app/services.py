"""
Excel import engine for Delivery Points.

Workflow: Upload → Analyze → Map → Validate/Preview → Confirm → Import.
Never silently overwrite; never auto-coerce free-form spreadsheet statuses.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook

from accounts.models import Organization
from imports_app.models import ImportJob
from tracker.activity_log import log_activity
from tracker.models import Module, Phase, Point, PointStatus

SYSTEM_FIELDS = [
    ("external_id", "Point ID (or leave blank → built from Annex + S.No.)", False),
    ("number", "S.No. / Number", True),
    ("module", "Module / Module-RFP", False),
    ("title", "Title", False),
    ("requirement", "Requirement / Finding / To Do's", False),
    ("status", "Status / Current Status", False),
    ("phase", "Phase (e.g. Remarks=Demo Day)", False),
    ("forbmax_response", "Forbmax Response", False),
    ("nimar_response", "NIMAR Response / QA Remarks", False),
    ("decision", "Decision", False),
    ("remarks", "Remarks / Developer remarks", False),
    ("annexure", "Annexure (A/B)", False),
    ("due_date", "Due Date", False),
    ("owner", "Owner", False),
]

# Real NIMAR annexure column names first, then generic aliases.
HEADER_ALIASES = {
    "external_id": [
        "point id",
        "pointid",
        "external_id",
        "external id",
        "req id",
        "requirement id",
    ],
    "number": [
        "s.no.",
        "s.no",
        "s no",
        "s no.",
        "sno",
        "sr.no",
        "sr no",
        "serial no",
        "serial number",
        "number",
        "no.",
        "#",
        "seq",
    ],
    "module": [
        "module-rfp",
        "module rfp",
        "module",
        "area",
        "functional area",
    ],
    "title": ["title", "short title", "name"],
    "requirement": [
        "to do's",
        "to dos",
        "todos",
        "todo",
        "finding",
        "findings",
        "requirement",
        "requirements",
        "explanation",
        "description",
        "details",
    ],
    "status": [
        "current status (nimar)",
        "current status",
        "status",
        "state",
        "implementation status",
    ],
    "phase": [
        "phase",
        "milestone",
        "delivery phase",
        "demo day",
    ],
    "forbmax_response": [
        "forbmax response",
        "forbmax",
        "response",
        "implementation note",
        "source response",
    ],
    "nimar_response": [
        "qa remarks",
        "qa remark",
        "nimar response",
        "client response",
        "nimar",
    ],
    "decision": ["decision", "acceptance", "client decision"],
    "remarks": [
        "developer’s remarks",
        "developer's remarks",
        "developer remarks",
        "remarks",
        "notes",
        "comments",
        "observation",
        "observations",
    ],
    "annexure": ["annexure", "annex", "category"],
    "due_date": ["due date", "due", "target date", "deadline"],
    "owner": ["owner", "owner email", "responsible", "assignee"],
}

HEADER_HINTS = ("s.no", "module-rfp", "module rfp", "requirement", "current status", "forbmax")
PHASE_LABELS = {
    "demo day",
    "demodday",
    "25%",
    "75%",
    "0.25",
    "0.75",
    "sla",
    "pct_25",
    "pct_75",
    "demo_day",
}

# Exact matches only — never used for free-form source values like "Not implemented"
SYSTEM_STATUS_EXACT = {
    "PLANNED": PointStatus.PLANNED,
    "SCOPE APPROVAL": PointStatus.SCOPE_APPROVAL,
    "SCOPE_APPROVAL": PointStatus.SCOPE_APPROVAL,
    "IN PROGRESS": PointStatus.IN_PROGRESS,
    "IN_PROGRESS": PointStatus.IN_PROGRESS,
    "AWAITING VERIFICATION": PointStatus.AWAITING_VERIFICATION,
    "AWAITING_VERIFICATION": PointStatus.AWAITING_VERIFICATION,
    "REWORK REQUESTED": PointStatus.REWORK_REQUESTED,
    "REWORK_REQUESTED": PointStatus.REWORK_REQUESTED,
    "VERIFIED & CLOSED": PointStatus.VERIFIED_CLOSED,
    "VERIFIED AND CLOSED": PointStatus.VERIFIED_CLOSED,
    "VERIFIED_CLOSED": PointStatus.VERIFIED_CLOSED,
}

# Label lookup for PointStatus
for value, label in PointStatus.choices:
    SYSTEM_STATUS_EXACT[label.upper()] = value
    SYSTEM_STATUS_EXACT[value.upper()] = value


def _cell_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _normalize_header(value) -> str:
    text = _cell_str(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _trim_headers(headers: list[str]) -> list[str]:
    """Drop trailing empty/ColumnN placeholders from sparse annexure sheets."""
    cleaned = []
    last_real = -1
    for i, h in enumerate(headers):
        text = _cell_str(h)
        if text and not re.fullmatch(r"Column\d+", text):
            last_real = i
        cleaned.append(text or f"Column{i + 1}")
    if last_real < 0:
        return cleaned
    return cleaned[: last_real + 1]


def _find_header_row(rows: list) -> int:
    """
    Prefer a real NIMAR header row (S.No. / Module-RFP / Current Status),
    skipping title rows like 'Annex-A'.
    """
    best_idx = 0
    best_score = -1
    for i, row in enumerate(rows[:25]):
        cells = [_normalize_header(c) for c in row if _cell_str(c)]
        if not cells:
            continue
        score = 0
        joined = " | ".join(cells)
        for hint in HEADER_HINTS:
            if any(hint == c or hint in c for c in cells):
                score += 3
        if "s.no" in joined or "module" in joined:
            score += 2
        # Title-only rows (single merged annex label) score low
        if len(cells) <= 2 and any("annex" in c for c in cells):
            score -= 5
        if score > best_score:
            best_score = score
            best_idx = i
    if best_score <= 0:
        for i, row in enumerate(rows[:20]):
            if any(_cell_str(c) for c in row):
                return i
    return best_idx


def annexure_code_from_sheet(sheet_name: str) -> str:
    text = (sheet_name or "").upper()
    if re.search(r"\bB\b", text) or "ANNEXURE B" in text or "ANNEX B" in text or "ANNEX-B" in text:
        return "B"
    if re.search(r"\bA\b", text) or "ANNEXURE A" in text or "ANNEX A" in text or "ANNEX-A" in text:
        return "A"
    m = re.search(r"ANNEX(?:URE)?[\s\-]*([A-Z])", text)
    if m:
        return m.group(1)
    return ""


def annexure_code_from_filename(filename: str) -> str:
    text = (filename or "").upper()
    # Prefer explicit Annex A/B token in filename
    m = re.search(r"ANNEX(?:URE)?[\s\-_]*([AB])\b", text)
    if m:
        return m.group(1)
    if re.search(r"\bANNEX(?:URE)?S?\b", text) and re.search(r"\bB\b", text):
        return "B"
    if re.search(r"\bANNEX(?:URE)?S?\b", text) and re.search(r"\bA\b", text):
        return "A"
    return ""


def normalize_serial(raw: str) -> str:
    text = _cell_str(raw)
    if not text:
        return ""
    try:
        num = float(text.replace(",", ""))
        if num.is_integer():
            return str(int(num))
        return str(num)
    except ValueError:
        return text


def compose_external_id(*, annexure: str, number: str, explicit: str = "") -> str:
    if _cell_str(explicit):
        return _cell_str(explicit)
    serial = normalize_serial(number)
    annex = _cell_str(annexure).upper()
    if annex and serial:
        return f"{annex}-{serial}"
    return serial


def _module_display_name(raw: str) -> str:
    """Module-RFP cells often look like 'Facial\\nRecognition\\nRFP Points: 5,22'."""
    text = _cell_str(raw)
    if not text:
        return ""
    text = re.split(r"\bRFP\s*Points?:", text, maxsplit=1, flags=re.I)[0]
    parts = [p.strip() for p in re.split(r"[\r\n]+", text) if p.strip()]
    name = " ".join(parts)
    return re.split(r"\s*\|\s*", name, maxsplit=1)[0].strip()


def _looks_like_serial(raw: str) -> bool:
    """True for annexure S.No. values (positive integers). Skips 0.75/SLA sub-headers."""
    text = _cell_str(raw)
    if not text:
        return False
    try:
        num = float(text.replace(",", ""))
        return num.is_integer() and num >= 1
    except ValueError:
        return False


def _is_junk_data_row(row: list[str]) -> bool:
    """Drop repeated header / payment-band rows under annexure column groups."""
    if not row or not any(_cell_str(c) for c in row):
        return True
    first = _normalize_header(row[0] if row else "")
    if first in {
        "s.no.",
        "s.no",
        "s no",
        "s no.",
        "sno",
        "module-rfp",
        "module rfp",
        "module",
        "0.75",
        "0.25",
        "75%",
        "25%",
        "sla",
    }:
        return True
    # Entire row looks like column labels
    labels = {_normalize_header(c) for c in row if _cell_str(c)}
    if labels & {"current status", "forbmax response", "module-rfp", "finding", "requirement"}:
        if not _looks_like_serial(row[0]):
            return True
    return False


def _column_values_look_like_phases(headers, data_rows, header_name: str) -> bool:
    if header_name not in headers:
        return False
    idx = headers.index(header_name)
    values = []
    for row in data_rows:
        if idx < len(row) and row[idx]:
            values.append(_normalize_header(row[idx]))
    if not values:
        return False
    phaseish = sum(1 for v in values if v in PHASE_LABELS or v.startswith("demo"))
    return (phaseish / len(values)) >= 0.5


def suggest_mapping(headers: list[str], data_rows: list[list[str]] | None = None) -> dict[str, str]:
    """Suggest system_field -> spreadsheet header using NIMAR-aware aliases."""
    mapping = {}
    used_headers = set()
    normalized = {_normalize_header(h): h for h in headers if _cell_str(h)}
    data_rows = data_rows or []

    for field, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias in normalized and normalized[alias] not in used_headers:
                mapping[field] = normalized[alias]
                used_headers.add(normalized[alias])
                break

    # NIMAR: Remarks often holds phase ("Demo Day"); QA Remarks holds commentary.
    remarks_header = normalized.get("remarks")
    qa_header = normalized.get("qa remarks") or normalized.get("qa remark")
    if remarks_header and _column_values_look_like_phases(headers, data_rows, remarks_header):
        mapping["phase"] = remarks_header
        if qa_header:
            # QA Remarks → NIMAR response; keep remarks free unless developer notes exist
            mapping["nimar_response"] = qa_header
            used_headers.add(qa_header)
            for key in ("developer’s remarks", "developer's remarks", "developer remarks"):
                if key in normalized:
                    mapping["remarks"] = normalized[key]
                    break
            else:
                mapping.pop("remarks", None)
        elif mapping.get("remarks") == remarks_header:
            for key in ("developer’s remarks", "developer's remarks", "developer remarks"):
                if key in normalized:
                    mapping["remarks"] = normalized[key]
                    break
            else:
                mapping.pop("remarks", None)

    # When both Requirement and Explanation exist: use Requirement as title only
    # if samples look like short labels; otherwise keep long findings as requirement.
    req_h = normalized.get("requirement")
    expl_h = normalized.get("explanation")
    if req_h and expl_h and mapping.get("requirement") == req_h:
        idx = headers.index(req_h)
        samples = [row[idx] for row in data_rows[:30] if idx < len(row) and row[idx]]
        avg_len = (sum(len(s) for s in samples) / len(samples)) if samples else 0
        if avg_len and avg_len <= 120:
            mapping["title"] = req_h
            mapping["requirement"] = expl_h
            used_headers.add(expl_h)
        else:
            # Long "Requirement" text → body; Explanation stays in source_metadata
            mapping["requirement"] = req_h
            mapping.pop("title", None)

    return mapping


def suggest_status_mapping(unique_statuses: list[str]) -> dict[str, str]:
    """
    Suggest only exact system-label/code matches.
    Free-form values (Not implemented, Partially Implemented, etc.) stay unmapped.
    """
    suggested = {}
    for raw in unique_statuses:
        key = _cell_str(raw)
        if not key:
            continue
        exact = SYSTEM_STATUS_EXACT.get(key.upper())
        if exact:
            suggested[key] = exact
    return suggested


def suggest_phase_mapping(unique_phases: list[str]) -> dict[str, str]:
    phases = {p.name.upper(): p.code for p in Phase.objects.filter(is_active=True)}
    phases.update({p.code.upper(): p.code for p in Phase.objects.filter(is_active=True)})
    # Common aliases
    phases.update(
        {
            "DEMO DAY": "DEMO_DAY",
            "DEMODAY": "DEMO_DAY",
            "25%": "PCT_25",
            "25": "PCT_25",
            "75%": "PCT_75",
            "75": "PCT_75",
            "SLA": "SLA",
        }
    )
    suggested = {}
    for raw in unique_phases:
        key = _cell_str(raw)
        if not key:
            continue
        code = phases.get(key.upper())
        if code:
            suggested[key] = code
    return suggested


def _unmerge_fill(ws):
    """Copy top-left value into all cells of each merged range."""
    merged = list(ws.merged_cells.ranges)
    for rng in merged:
        min_row, min_col, max_row, max_col = rng.min_row, rng.min_col, rng.max_row, rng.max_col
        top = ws.cell(min_row, min_col).value
        try:
            ws.unmerge_cells(str(rng))
        except Exception:
            pass
        for r in range(min_row, max_row + 1):
            for c in range(min_col, max_col + 1):
                if ws.cell(r, c).value is None:
                    ws.cell(r, c).value = top


def analyze_workbook(file_obj, *, filename: str = "") -> dict:
    try:
        wb = load_workbook(file_obj, data_only=True, read_only=False)
    except Exception as exc:
        raise ValidationError(f"Unable to import file: malformed workbook structure. ({exc})") from exc

    file_annex = annexure_code_from_filename(filename)
    sheets = []
    for name in wb.sheetnames:
        ws = wb[name]
        _unmerge_fill(ws)
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            sheets.append({"name": name, "headers": [], "row_count": 0, "sample_rows": []})
            continue
        header_idx = _find_header_row(rows)
        raw_headers = [_cell_str(c) for c in rows[header_idx]]
        headers = _trim_headers(raw_headers)
        data_rows = []
        for row in rows[header_idx + 1 :]:
            values = [_cell_str(c) for c in row[: len(headers)]]
            if _is_junk_data_row(values):
                continue
            data_rows.append(values)
        sample = []
        for row in data_rows[:5]:
            sample.append({headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))})
        sheets.append(
            {
                "name": name,
                "headers": headers,
                "row_count": len(data_rows),
                "header_row": header_idx + 1,
                "annexure_guess": annexure_code_from_sheet(name) or file_annex,
                "sample_rows": sample,
            }
        )
    return {"sheets": sheets, "sheet_names": wb.sheetnames, "annexure_guess": file_annex}


def _read_sheet_rows(file_obj, sheet_name: str) -> tuple[list[str], list[list[str]]]:
    try:
        wb = load_workbook(file_obj, data_only=True, read_only=False)
    except Exception as exc:
        raise ValidationError(f"Unable to import file: malformed workbook structure. ({exc})") from exc
    if sheet_name not in wb.sheetnames:
        raise ValidationError(f"Sheet '{sheet_name}' not found in workbook.")
    ws = wb[sheet_name]
    _unmerge_fill(ws)
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], []
    header_idx = _find_header_row(rows)
    headers = _trim_headers([_cell_str(c) for c in rows[header_idx]])
    data_rows = []
    for row in rows[header_idx + 1 :]:
        values = [_cell_str(c) for c in row[: len(headers)]]
        if _is_junk_data_row(values):
            continue
        data_rows.append(values)
    return headers, data_rows


def create_import_job(*, actor, uploaded_file) -> ImportJob:
    if not actor.is_forbmax and not actor.is_superuser:
        raise ValidationError("Only Forbmax users can import spreadsheets.")
    name = getattr(uploaded_file, "name", "") or "upload.xlsx"
    if not name.lower().endswith(".xlsx"):
        raise ValidationError("Unable to import file: only .xlsx workbooks are supported.")

    job = ImportJob(
        file=uploaded_file,
        original_filename=name,
        uploaded_by=actor,
        status=ImportJob.Status.UPLOADED,
    )
    job.save()

    try:
        job.file.open("rb")
        analysis = analyze_workbook(job.file, filename=name)
        job.file.close()
    except ValidationError as exc:
        job.status = ImportJob.Status.FAILED
        job.error_summary = {"detail": list(exc.messages) if hasattr(exc, "messages") else [str(exc)]}
        job.save(update_fields=["status", "error_summary", "updated_at"])
        raise

    job.analysis = analysis
    job.status = ImportJob.Status.ANALYZED
    job.save(update_fields=["analysis", "status", "updated_at"])
    return job


def select_sheet(*, job: ImportJob, sheet_name: str) -> ImportJob:
    sheets = {s["name"]: s for s in (job.analysis or {}).get("sheets", [])}
    if sheet_name not in sheets:
        raise ValidationError(f"Sheet '{sheet_name}' was not found in the uploaded workbook.")

    sheet = sheets[sheet_name]
    headers = sheet["headers"]
    if not headers:
        raise ValidationError("Unable to import file: selected sheet has no headers.")

    # Collect unique status/phase values from sample + full sheet
    job.file.open("rb")
    headers2, data_rows = _read_sheet_rows(job.file, sheet_name)
    job.file.close()
    headers = headers2 or headers

    suggested = suggest_mapping(headers, data_rows)
    annex_guess = (
        annexure_code_from_sheet(sheet_name)
        or (job.analysis or {}).get("annexure_guess")
        or annexure_code_from_filename(job.original_filename or "")
    )
    status_col = suggested.get("status")
    phase_col = suggested.get("phase")
    status_idx = headers.index(status_col) if status_col in headers else None
    phase_idx = headers.index(phase_col) if phase_col in headers else None

    unique_statuses = []
    unique_phases = []
    seen_s, seen_p = set(), set()
    for row in data_rows:
        if status_idx is not None and status_idx < len(row):
            v = row[status_idx]
            # Keep full free-form status text for explicit mapping UI
            if v and v not in seen_s:
                seen_s.add(v)
                unique_statuses.append(v)
        if phase_idx is not None and phase_idx < len(row):
            v = row[phase_idx]
            if v and v not in seen_p:
                seen_p.add(v)
                unique_phases.append(v)

    job.sheet_name = sheet_name
    job.total_rows = len(data_rows)
    job.column_mapping = suggested
    job.status_mapping = suggest_status_mapping(unique_statuses)
    job.phase_mapping = suggest_phase_mapping(unique_phases)
    job.analysis = {
        **(job.analysis or {}),
        "selected_sheet": sheet_name,
        "headers": headers,
        "annexure_guess": annex_guess,
        "id_strategy": (
            "external_id_column"
            if suggested.get("external_id")
            else "annex_plus_sno"
        ),
        "unique_statuses": unique_statuses[:80],
        "unique_phases": unique_phases,
        "suggested_column_mapping": suggested,
        "suggested_status_mapping": job.status_mapping,
        "suggested_phase_mapping": job.phase_mapping,
        "system_fields": [
            {"field": f, "label": label, "required": req} for f, label, req in SYSTEM_FIELDS
        ],
        "system_statuses": [{"value": v, "label": l} for v, l in PointStatus.choices],
        "system_phases": [
            {"code": p.code, "name": p.name} for p in Phase.objects.filter(is_active=True)
        ],
        "notes": (
            "NIMAR annexure sheets detected-style mapping: Point ID is built as "
            f"{annex_guess or 'A'}-{{S.No.}} when no Point ID column exists. "
            "Free-form Current Status values must be mapped explicitly."
        ),
    }
    job.status = ImportJob.Status.ANALYZED
    job.save()
    return job


def _parse_due_date(raw: str):
    if not raw:
        return None, None
    # Excel serial dates sometimes come as numbers already converted
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw[:10], fmt).date(), None
        except ValueError:
            continue
    # openpyxl may give "2026-10-02 00:00:00"
    try:
        return datetime.fromisoformat(raw.replace("Z", "")).date(), None
    except ValueError:
        return None, f"Invalid date: {raw}"


def _preview_rows_from_sheet(*, job: ImportJob, headers: list[str], data_rows: list[list[str]]) -> list[dict]:
    """Build CREATE/UPDATE/SKIP/FAIL preview rows for one sheet."""
    mapping = job.column_mapping or {}
    header_index = {h: i for i, h in enumerate(headers)}
    annex_default = (
        (job.analysis or {}).get("annexure_guess")
        or annexure_code_from_sheet(job.sheet_name or "")
        or "A"
    )
    header_row = 1
    for sheet in (job.analysis or {}).get("sheets", []):
        if sheet.get("name") == job.sheet_name:
            header_row = sheet.get("header_row") or 1
            break

    def get_field(row, field):
        header = mapping.get(field)
        if not header or header not in header_index:
            return ""
        idx = header_index[header]
        return row[idx] if idx < len(row) else ""

    mapped_headers = set(mapping.values())
    existing = {p.external_id: p for p in Point.objects.select_related("module", "phase", "owner")}
    seen_ids: dict[str, int] = {}
    preview_rows = []

    for offset, row in enumerate(data_rows):
        row_num = header_row + 1 + offset
        number = normalize_serial(get_field(row, "number"))
        explicit_id = get_field(row, "external_id").strip()
        # Skip payment sub-header rows (0.75 / 0.25 / SLA) and blank serials
        if not explicit_id and mapping.get("number") and not _looks_like_serial(number):
            continue

        annexure = (get_field(row, "annexure") or annex_default).strip().upper()
        external_id = compose_external_id(
            annexure=annexure,
            number=number,
            explicit=explicit_id,
        )
        raw_status = get_field(row, "status")
        raw_phase = get_field(row, "phase")
        module_name = _module_display_name(get_field(row, "module"))
        requirement = get_field(row, "requirement")
        title = get_field(row, "title")
        due_raw = get_field(row, "due_date")
        due_date, due_err = _parse_due_date(due_raw)

        source_meta = {}
        for i, h in enumerate(headers):
            if h in mapped_headers:
                continue
            val = row[i] if i < len(row) else ""
            if val:
                source_meta[h] = val

        errors = []
        action = "CREATE"
        conflicts = {}
        mapped_status = None
        mapped_phase = None

        if not external_id:
            errors.append("Missing Point ID (map Point ID or S.No.).")
            action = "FAIL"
        elif external_id in seen_ids:
            errors.append(f"Duplicate Point ID in file (also on row {seen_ids[external_id]}).")
            action = "FAIL"
        else:
            seen_ids[external_id] = row_num

        if raw_status:
            mapped_status = (job.status_mapping or {}).get(raw_status)
            if not mapped_status:
                errors.append(
                    f"Status '{raw_status}' is not mapped to a system status. "
                    "Free-form values must be mapped explicitly."
                )
                action = "FAIL"
            elif mapped_status not in PointStatus.values:
                errors.append(f"Unsupported mapped status: {mapped_status}.")
                action = "FAIL"
        else:
            mapped_status = PointStatus.PLANNED

        if raw_phase:
            mapped_phase = (job.phase_mapping or {}).get(raw_phase)
            if not mapped_phase:
                errors.append(f"Phase '{raw_phase}' is not mapped.")
                action = "FAIL"
            elif not Phase.objects.filter(code=mapped_phase).exists():
                errors.append(f"Unknown phase code: {mapped_phase}.")
                action = "FAIL"

        if due_err:
            errors.append(due_err)
            action = "FAIL"

        existing_point = existing.get(external_id) if external_id else None
        if action != "FAIL" and existing_point:
            action = "UPDATE"

            def diff(field, new_val, old_val):
                if (new_val or "") != (old_val or ""):
                    conflicts[field] = {"old": old_val or "", "new": new_val or ""}

            diff("status", mapped_status, existing_point.status)
            diff("requirement", requirement, existing_point.requirement)
            diff("title", title, existing_point.title)
            diff("forbmax_response", get_field(row, "forbmax_response"), existing_point.forbmax_response)
            diff("nimar_response", get_field(row, "nimar_response"), existing_point.nimar_response)
            diff("decision", get_field(row, "decision"), existing_point.decision)
            diff("remarks", get_field(row, "remarks"), existing_point.remarks)
            if module_name:
                old_mod = existing_point.module.name if existing_point.module_id else ""
                diff("module", module_name, old_mod)
            if mapped_phase:
                old_ph = existing_point.phase.code if existing_point.phase_id else ""
                diff("phase", mapped_phase, old_ph)
            if not conflicts:
                action = "SKIP"

        if action == "FAIL" and not errors:
            errors.append("Validation failed.")

        preview_rows.append(
            {
                "row": row_num,
                "external_id": external_id,
                "action": action,
                "errors": errors,
                "conflicts": conflicts,
                "values": {
                    "external_id": external_id,
                    "module": module_name,
                    "title": title,
                    "requirement": requirement,
                    "status": mapped_status,
                    "status_source": raw_status,
                    "phase": mapped_phase,
                    "phase_source": raw_phase,
                    "forbmax_response": get_field(row, "forbmax_response"),
                    "nimar_response": get_field(row, "nimar_response"),
                    "decision": get_field(row, "decision"),
                    "remarks": get_field(row, "remarks"),
                    "annexure": annexure,
                    "number": number,
                    "due_date": due_date.isoformat() if due_date else "",
                    "owner": get_field(row, "owner"),
                    "source_metadata": source_meta,
                },
            }
        )
    return preview_rows


def build_preview(
    *,
    job: ImportJob,
    column_mapping: dict | None = None,
    status_mapping: dict | None = None,
    phase_mapping: dict | None = None,
) -> ImportJob:
    if not job.sheet_name:
        raise ValidationError("Select a sheet before previewing.")

    if column_mapping is not None:
        job.column_mapping = column_mapping
    if status_mapping is not None:
        job.status_mapping = status_mapping
    if phase_mapping is not None:
        job.phase_mapping = phase_mapping

    mapping = job.column_mapping or {}
    if not mapping.get("external_id") and not mapping.get("number"):
        raise ValidationError(
            {
                "external_id": "Map Point ID, or map S.No. so IDs can be built as Annex-{S.No.}.",
                "number": "S.No. is required when Point ID column is not mapped.",
            }
        )

    job.file.open("rb")
    headers, data_rows = _read_sheet_rows(job.file, job.sheet_name)
    job.file.close()

    preview_rows = _preview_rows_from_sheet(job=job, headers=headers, data_rows=data_rows)
    counts = {"CREATE": 0, "UPDATE": 0, "SKIP": 0, "FAIL": 0}
    for row in preview_rows:
        counts[row["action"]] = counts.get(row["action"], 0) + 1

    file_errors = []
    if counts["FAIL"]:
        fail_msgs = [r["errors"][0] for r in preview_rows if r["action"] == "FAIL" and r["errors"]]
        if any("Duplicate Point ID" in m for m in fail_msgs):
            file_errors.append("Unable to import file: duplicate point IDs found.")

    job.preview_summary = {
        "counts": counts,
        "rows": preview_rows[:500],
        "row_count": len(preview_rows),
        "truncated": len(preview_rows) > 500,
        "file_errors": file_errors,
        "has_failures": counts["FAIL"] > 0,
        "has_updates": counts["UPDATE"] > 0,
    }
    job.error_summary = {"file_errors": file_errors, "fail_count": counts["FAIL"]}
    job.total_rows = len(preview_rows)
    job.status = ImportJob.Status.PREVIEWED
    job.save()
    return job


@transaction.atomic
def confirm_import(*, job: ImportJob, actor) -> ImportJob:
    if job.status not in {ImportJob.Status.PREVIEWED, ImportJob.Status.VALIDATED}:
        raise ValidationError("Import must be previewed before confirmation.")
    if not job.preview_summary or not job.preview_summary.get("rows"):
        # Rebuild if preview rows truncated or missing — rebuild full preview
        job = build_preview(job=job)

    preview = job.preview_summary or {}
    if preview.get("has_failures"):
        raise ValidationError(
            preview.get("file_errors")
            and preview["file_errors"][0]
            or "Unable to import file: fix FAIL rows before confirming."
        )

    # Rebuild full preview for apply (not truncated)
    full = build_preview(job=job)
    rows = (full.preview_summary or {}).get("rows") or []
    # If truncated, re-read from file
    if (full.preview_summary or {}).get("truncated"):
        # Force full apply path from file using same mappings
        rows = _build_all_preview_rows(job)

    org = Organization.objects.filter(code=Organization.Code.FORBMAX).first()
    created = updated = skipped = failed = 0

    for row in rows:
        action = row["action"]
        values = row["values"]
        if action == "FAIL":
            failed += 1
            continue
        if action == "SKIP":
            skipped += 1
            continue

        external_id = values["external_id"]
        module = None
        if values.get("module"):
            module, _ = Module.objects.get_or_create(
                name=values["module"], defaults={"is_active": True}
            )
        phase = None
        if values.get("phase"):
            phase = Phase.objects.filter(code=values["phase"]).first()

        defaults = {
            "organization": org,
            "module": module,
            "phase": phase,
            "title": values.get("title") or "",
            "requirement": values.get("requirement") or "",
            "status": values.get("status") or PointStatus.PLANNED,
            "forbmax_response": values.get("forbmax_response") or "",
            "nimar_response": values.get("nimar_response") or "",
            "decision": values.get("decision") or "",
            "remarks": values.get("remarks") or "",
            "annexure": values.get("annexure") or "",
            "number": values.get("number") or "",
            "updated_by": actor,
            "source_metadata": values.get("source_metadata") or {},
        }
        if values.get("due_date"):
            defaults["due_date"] = date.fromisoformat(values["due_date"])

        # Scope approved if status is past scope approval
        if defaults["status"] in {
            PointStatus.IN_PROGRESS,
            PointStatus.AWAITING_VERIFICATION,
            PointStatus.REWORK_REQUESTED,
            PointStatus.VERIFIED_CLOSED,
        }:
            defaults["scope_approved"] = True

        if action == "CREATE":
            point = Point.objects.create(external_id=external_id, **defaults)
            created += 1
            log_activity(
                actor=actor,
                entity_type="Point",
                entity_id=external_id,
                action="import_create",
                new_value={"status": point.status, "source": job.original_filename},
                message=f"Created via Excel import #{job.pk}",
                point_external_id=external_id,
            )
        else:
            point = Point.objects.get(external_id=external_id)
            old_status = point.status
            for k, v in defaults.items():
                setattr(point, k, v)
            # Merge source metadata
            meta = point.source_metadata or {}
            meta.update(defaults.get("source_metadata") or {})
            point.source_metadata = meta
            point.save()
            updated += 1
            log_activity(
                actor=actor,
                entity_type="Point",
                entity_id=external_id,
                action="import_update",
                old_value={"status": old_status},
                new_value={"status": point.status, "source": job.original_filename},
                message=f"Updated via Excel import #{job.pk}",
                point_external_id=external_id,
            )

    job.created_count = created
    job.updated_count = updated
    job.skipped_count = skipped
    job.failed_count = failed
    job.status = ImportJob.Status.COMPLETED
    job.completed_at = timezone.now()
    job.save()
    return job


def _build_all_preview_rows(job: ImportJob) -> list[dict]:
    """Rebuild full preview rows (no truncation) for confirm."""
    job.file.open("rb")
    headers, data_rows = _read_sheet_rows(job.file, job.sheet_name)
    job.file.close()
    return _preview_rows_from_sheet(job=job, headers=headers, data_rows=data_rows)


def job_to_dict(job: ImportJob) -> dict:
    return {
        "id": job.pk,
        "original_filename": job.original_filename,
        "status": job.status,
        "status_label": job.get_status_display(),
        "sheet_name": job.sheet_name,
        "total_rows": job.total_rows,
        "created_count": job.created_count,
        "updated_count": job.updated_count,
        "failed_count": job.failed_count,
        "skipped_count": job.skipped_count,
        "column_mapping": job.column_mapping,
        "status_mapping": job.status_mapping,
        "phase_mapping": job.phase_mapping,
        "analysis": job.analysis,
        "preview_summary": job.preview_summary,
        "error_summary": job.error_summary,
        "uploaded_by": job.uploaded_by.name if job.uploaded_by_id else None,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
