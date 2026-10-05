# NIMAR Delivery & Client Closure Tracker — Implementation Todo

Lightweight internal + client-facing delivery tracker for **Forbmax** (manages) and **NIMAR** (reviews, raises issues, verifies).

**Stack (locked):** Django + PostgreSQL + server-rendered HTML/CSS/vanilla JS + openpyxl + Chart.js. Monolith only. Everything runs in Docker.

**Source of truth:** `NIMAR_Delivery_Client_Closure_Tracker_PRD.txt`  
**Visual reference:** NIMAR Deployment Plan.html (compact control-room UI)

**Success:** Forbmax can Import → Manage → Update → Resolve → Report. NIMAR can Login → Review → Comment → Raise Issue → Verify. Spreadsheet is no longer the day-to-day tracker.

---

## Phase 1 — Foundation, Docker, Auth, and Data Model ✅ COMPLETED

Stand up the project so every later phase runs inside Docker from day one. Schema must already support Demo Day, 25%, 75%, and SLA even if only Demo Day is activated first.

**Completed:** 2026-10-02 — `docker compose up` healthy; `/health` OK; seeded logins for all three roles.

### Docker (required from the start)

- [x] `Dockerfile` for the Django app (dev + production-ready target)
- [x] `docker-compose.yml` for local/dev: `web` (Django), `db` (PostgreSQL), `nginx` (reverse proxy)
- [x] Named volumes for Postgres data and uploaded evidence
- [x] `.env.example` for `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, org/seed flags
- [x] One-command bring-up: `docker compose up --build`
- [x] Django migrate + seed on first boot (or documented `manage.py` entry via compose)
- [x] `/health` endpoint (app + DB check) for nginx and later monitoring
- [x] `.dockerignore` (no secrets, no local venv, no `__pycache__`)
- [x] README: how to start, migrate, create admin, and log in — no host Python/Postgres required

### Project scaffold

- [x] Django project + apps: `accounts`, `tracker`, `imports_app`, `metrics`, `audit`
- [x] Settings split: `base` / `dev` / `prod` (prod behind env vars)
- [x] CSRF, secure cookies, password hashing enabled
- [x] Static files collected through Docker/nginx
- [x] Error pages that never leak stack traces to users

### Organizations, users, roles

- [x] `Organization` (Forbmax, NIMAR)
- [x] `User`: name, email, organization, role, active, timestamps
- [x] Roles: Forbmax Admin, Forbmax Member, NIMAR User
- [x] Browser login / logout (`POST /api/auth/login/`, `POST /api/auth/logout/` + session views)
- [x] All non-public pages require authentication
- [x] Backend authorization helpers (`accounts.permissions`) for write gates
- [x] Organization isolation helper on querysets
- [x] Seed: Forbmax Admin, Forbmax Member, NIMAR User

### Core schema (create now, use later)

- [x] `Phase` — Demo Day, 25%, 75%, SLA (name, code, dates, order, active)
- [x] `Module`
- [x] `Point` — all PRD fields including `external_id`, annexure, number, title, requirement, status, Forbmax/NIMAR responses, decision, remarks, owner, due date, source-metadata/notes for unmapped spreadsheet columns
- [x] `Issue`
- [x] `Comment`
- [x] `Attachment`
- [x] `ActivityLog` (immutable)
- [x] `ImportJob`
- [x] Indexes: Point (`external_id`, `phase_id`, `module_id`, `status`, `owner_id`, `due_date`, `updated_at`); Issue (`point_id`, `status`); ActivityLog (`entity_type`/`entity_id`, `created_at`)
- [x] Unique `Point.external_id`
- [x] Status enum: Planned → Scope Approval → In Progress → Awaiting Verification → Rework Requested → Verified & Closed
- [x] Seed phases, statuses, and a small Demo Day fixture set

### Exit criteria

- [x] `docker compose up` starts nginx + Django + Postgres
- [x] Login works for all three roles
- [x] Schema is migrated and seeded
- [x] `/health` returns OK

---

## Phase 2 — Delivery Points, Register, Drawer, and Status Workflow ✅ COMPLETED

Make the point the operational source of truth. Control-room UI starts here.

**Completed:** 2026-10-02 — register + drawer live; status gates and role field permissions enforced; point edits audited.

### Point register

- [x] Register table: ID, module, title/requirement, phase, status, owner, due date, issue indicator, updated time
- [x] Search: ID, title, requirement, module, responses, decisions, remarks, issue text
- [x] Filters (AND): phase, module, status, annexure, issue status, owner; optional due/updated date
- [x] Sort: ID, module, phase, status, due date, updated date
- [x] Pagination
- [x] Empty state: “No points match the selected filters”
- [x] APIs: `GET /api/points`, `GET /api/points/{id}`, `POST /api/points`, `PATCH /api/points/{id}`
- [x] Lookups: `GET /api/phases`, `GET /api/modules`, `GET /api/statuses`

### Point detail drawer

- [x] Side drawer (preferred over a full page)
- [x] Header: ID, module, phase, status, close
- [x] Full requirement, Forbmax response, NIMAR response, decision, remarks
- [x] Owner and due date
- [x] Placeholders for issues, evidence, activity (wired in Phase 3)
- [x] Compact control-room styling from the reference HTML: KPI strip later, filter rail, compact table, tabs, small buttons — no marketing UI

### Status and phase rules

- [x] Lifecycle: Planned → Scope Approval → In Progress → Awaiting Verification → Verified & Closed
- [x] Rework path: Awaiting Verification → Rework Requested → In Progress → …
- [x] Block In Progress until required scope approval is recorded
- [x] Closed only after NIMAR verification/acceptance
- [x] Closed points require verification/acceptance fields
- [x] Clear validation errors, e.g. “This point cannot move to In Progress because scope approval is pending.”
- [x] Forbmax Admin: full field access; Forbmax Member: operational updates; NIMAR User: view + client response where enabled — cannot edit restricted internal fields

### Audit on points

- [x] Log status changes, field edits, owner changes, decisions (actor, org, old/new, timestamp)

### Exit criteria

- [x] Seeded/manual points appear in the register
- [x] Drawer opens from a row
- [x] Status transitions enforce rules
- [x] NIMAR cannot change restricted Forbmax fields
- [x] Point edits appear in activity history

---

## Phase 3 — Issues, Comments, Evidence, and Activity History ✅ COMPLETED

Collaboration stays simple. Every issue belongs to one point.

**Completed:** 2026-10-02 — issues/comments/evidence APIs + drawer UI; aggregated history; uploads on Docker volume.

### Issues

- [x] Fields: ID, point, title, description, status, raised by, assigned to, created/updated, resolved at
- [x] Issue statuses: Open / Acknowledged / In Progress / Resolved / Closed
- [x] Closed issues require resolver + `resolved_at`
- [x] NIMAR: open point → raise issue → describe → attach evidence → submit
- [x] Forbmax: review → acknowledge → work → respond → resolve
- [x] NIMAR verifies/closes where permitted
- [x] APIs: `GET /api/issues`, `GET /api/issues/{id}`, `POST /api/issues`, `PATCH /api/issues/{id}`
- [x] Issue indicator on register rows
- [x] Empty state: “No open issues” (list shows “No issues yet.” when none exist)

### Comments

- [x] Chronological comments on a point or issue (author, timestamp)
- [x] Optional attachment on a comment (via issue/point evidence on create)
- [x] `POST /api/points/{id}/comments` (and issue equivalent)
- [x] Not a chat platform — keep it linear and small

### Evidence and attachments

- [x] Label, file or URL, type, uploader, timestamp
- [x] Categories for scope / verification links (lightweight, as in the reference UI)
- [x] Store files on a Docker volume (object-storage-ready path); metadata in Postgres
- [x] Validate type and size; reject unsafe uploads
- [x] Evidence panel in the point drawer

### Activity / audit (complete)

- [x] Also log: issue create/status, comments, evidence changes
- [x] `GET /api/points/{id}/history`
- [x] Drawer history tab
- [x] Empty state: “No activity recorded yet”
- [x] Answer: who changed what, when, old vs new

### Role-specific experience (first cut)

- [x] NIMAR: progress, open issues, recent updates, points waiting for NIMAR — no Forbmax admin chrome
- [x] Forbmax: remaining work, overdue, rework, client-pending, open issues, management controls by role

### Exit criteria

- [x] NIMAR can raise an issue with evidence
- [x] Forbmax can acknowledge, resolve, and comment
- [x] History shows the full trail
- [x] Uploads persist across container restarts (volume)

---

## Phase 4 — Excel Import, Export, and Spreadsheet Migration ✅ COMPLETED

Excel remains the migration and backup format. The database becomes the operational source after confirm.

**Completed:** 2026-10-05 — import wizard + export; free-form statuses require explicit mapping; re-import previews UPDATE/SKIP.

### Import workflow

- [x] Upload → Analyze → Map columns → Validate → Preview → Confirm → Import
- [x] `.xlsx` only for MVP (`openpyxl`)
- [x] Detect workbook, sheets, headers, row count; user picks the sheet
- [x] Do not assume a clean sheet (merged cells, free-form statuses, extra columns)
- [x] Column mapping UI (Point ID → `external_id`, Module, Requirement, Status, Phase, Response, Decision, Remarks, …)
- [x] Map free-form source statuses explicitly; never auto-coerce “Not implemented / Partially Implemented / Implemented” into system statuses
- [x] Unmapped columns preserved in notes / source-metadata
- [x] Validation: duplicate IDs, missing IDs, bad phase/status, invalid dates, empty required fields, malformed workbook, new vs existing
- [x] Preview action per row: CREATE / UPDATE / SKIP / FAIL
- [x] Conflicts show old vs new and require confirmation (no silent overwrite)
- [x] APIs: `POST /api/import/excel`, `GET /api/import/{id}`, `POST /api/import/{id}/confirm`
- [x] Import history: file name, uploader, time, totals (created/updated/failed), final status
- [x] Empty state: “No spreadsheet has been imported”
- [x] User-facing errors, e.g. “Unable to import file: duplicate point IDs found.”

### Export

- [x] Export all points
- [x] Export the current filtered set
- [x] Phase-specific and issue-specific export where useful
- [x] Include major operational fields + update timestamps
- [x] `GET /api/export/excel`

### Migration checklist (operational, not extra product)

- [x] Inspect official workbooks (headers, sheets, duplicates, dates) — process documented in `docs/MIGRATION_CHECKLIST.md`
- [x] Confirm canonical mapping
- [x] Import current Demo Day dataset — verified with representative sample workbook in Docker
- [x] Spot-check records against the frozen source sheet — checklist step for ops
- [x] Keep the original spreadsheet as a frozen reference copy — checklist step for ops

### Exit criteria

- [x] A real (or representative) xlsx can be previewed and confirmed inside Docker
- [x] Re-import of the same IDs is an explicit UPDATE, not a silent overwrite
- [x] Filtered export matches the register
- [x] Import job history is visible to Forbmax Admin

---

## Phase 5 — Dashboard, Metrics, and Client vs Forbmax Views ✅ COMPLETED

Management reporting from relational data only. No analytics platform.

**Completed:** 2026-10-05 — role-aware dashboard + metrics page (Chart.js) + metrics APIs.

### Dashboard

- [x] KPI cards: total, closed, open, in progress, awaiting NIMAR verification, rework requested, open issues, overdue, overall completion %
- [x] Progress by phase
- [x] Progress by module
- [x] Responsibility: waiting for Forbmax / waiting for NIMAR
- [x] Issue summary
- [x] Completion trend + points closed over time + issues opened vs resolved (Chart.js)
- [x] In-app counters / visual indicators (no notification product)
- [x] Loading, error, and empty states

### Metrics page

- [x] Overall: total, closed, open, in progress, progress %, overdue, open/resolved issues
- [x] Phase: total, planned, in progress, awaiting verification, rework, closed, completion %
- [x] Module: total, completed, open, issues, completion %
- [x] Responsibility: waiting Forbmax, waiting NIMAR, awaiting verification, rework
- [x] Time: avg/median resolution, avg NIMAR response time, oldest open issue
- [x] Trend: completion, points closed, issues opened vs resolved
- [x] Definitions: Completion % = Closed / Total × 100; Open = not Verified & Closed; Overdue = due date past and not closed; Open Issue = not Closed
- [x] APIs: `GET /api/metrics/overview`, `/phases`, `/modules`, `/issues`

### Experience polish

- [x] NIMAR first screen: overall progress, phase progress, open issues, recent updates, items needing NIMAR review
- [x] Forbmax first screen: remaining work, overdue, rework, client-pending, open issues, phase/module progress
- [x] Desktop/laptop/tablet usable; mobile functional, not mobile-first
- [x] UI language matches the reference control-room HTML

### Exit criteria

- [x] Dashboard numbers match the database for seeded + imported data
- [x] Filters on the register and metrics stay consistent
- [x] NIMAR never sees Forbmax admin/import/user-management controls

---

## Phase 6 — Visualization, Users, Production Docker, Tests, and Hardening ✅ COMPLETED

Finish the MVP: views, admin, production shape, and proof it is safe to use.

**Completed:** 2026-10-05 — Kanban/timeline, user admin, prod Compose + backups, pytest suite green in Docker.

### Kanban and timeline

- [x] Kanban by the six statuses; card: ID, module, title/short requirement, phase, due date, issue count
- [x] Status change via dropdown (drag-and-drop optional, skip if it adds complexity)
- [x] Lightweight Gantt/timeline: phase dates, milestones, progress, point counts, overdue — no task dependencies

### User management

- [x] Forbmax Admin: create/invite, deactivate, change role, manage access
- [x] List: name, email, organization, role, active/inactive
- [x] NIMAR users cannot manage other users

### Production Docker and deployment

- [x] Production `docker-compose.prod.yml` (or prod overlay): gunicorn/uwsgi, nginx TLS, Postgres, evidence volume
- [x] Internet → DNS → HTTPS/nginx → Django → PostgreSQL + storage
- [x] TLS/HTTPS in production; HTTP-only + secure cookies
- [x] NIMAR access is a normal HTTPS URL — no VPN, local install, Docker, or DB credentials on the client
- [x] Daily Postgres backup job in Compose (or documented cron sidecar) + retention
- [x] Evidence/storage included in backup
- [x] Documented restore procedure (tested once)
- [x] Logs: app errors, auth failures, import failures, permission failures, DB errors, unexpected exceptions
- [x] `/health` used by the proxy

### Tests (run in Docker)

- [x] Unit: metrics, status transitions, phase logic, permissions, import mapping, validation, issue lifecycle
- [x] Integration: login, point CRUD, issue create/update/resolve, Excel import/export, role permissions
- [x] Permission matrix:
  - [x] Forbmax Admin can administer
  - [x] Forbmax Member can operate but not configure users/phases/imports policy
  - [x] NIMAR User can view + raise issues, cannot edit restricted internal fields
- [x] `docker compose run --rm web pytest` (or project equivalent) is the only test entry point

### Acceptance sweep

- [x] Auth: login binds organization + role
- [x] Points: imported points are searchable/filterable; authorized updates work
- [x] Phases: Demo Day, 25%, 75%, SLA use the same model (activate remaining stages without a new system)
- [x] Status lifecycle + validation as specified
- [x] Issues: NIMAR raises, Forbmax resolves, history retained
- [x] Import: xlsx upload, sheet, map, validate, preview, confirm, results
- [x] Export: all or filtered
- [x] Metrics/dashboard match DB
- [x] Audit: actor + timestamp on important changes
- [x] UI consistent with the deployment-plan reference
- [x] Client access over HTTPS with no special infrastructure

### Explicitly out of scope (do not build)

- Full PM / dependencies / resources / timesheets
- CRM, billing, procurement
- Workflow builders, notification platform, microservices
- Redis/Celery, WebSockets, Elasticsearch, separate analytics
- Native apps, complex multi-tenant SaaS
- Email notifications (optional later: issue raised, resolved, response required, overdue)

### Exit criteria

- [x] Full stack runs from Docker only
- [x] Demo Day is operational end-to-end
- [x] 25% / 75% / SLA are in the same engine and can be turned on without a rewrite
- [x] Tests pass in CI/Docker
- [x] Backup + restore documented
- [x] Ready for a real NIMAR HTTPS URL

---

## Phase map (PRD → this plan)

| Phase | PRD sections covered |
| --- | --- |
| 1 Foundation + Docker | 6–8, 10–11, 28–32, 36–38, 49–51, 58 |
| 2 Points + workflow | 9, 12, 14–15, 25–26, 33, 39–40 |
| 3 Issues + evidence + audit | 16–19, 35, 43–44 |
| 4 Excel import/export | 20–21, 34, 45–47 |
| 5 Dashboard + metrics | 13, 22, 41–44 |
| 6 Views + prod + tests | 23–24, 28, 49–54, 55 Release 2–3 |

PRD Release 1 (Demo Day Tracker) = Phases 1–5.  
PRD Release 2–3 (Kanban, Gantt, richer ops, later lifecycle activation) = Phase 6.
