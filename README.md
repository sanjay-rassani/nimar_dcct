# NIMAR Delivery & Client Closure Tracker

Lightweight Django + PostgreSQL tracker for Forbmax and NIMAR. Everything runs in Docker.

## Stack

- Django (server-rendered HTML/CSS/vanilla JS)
- PostgreSQL 16
- Nginx reverse proxy
- openpyxl (Excel, later phases)
- Chart.js (metrics, later phases)

## Quick start (no host Python/Postgres required)

```bash
cp .env.example .env   # already present for local dev
docker compose up --build
```

Open:

- App: http://localhost/
- Health: http://localhost/health/
- Django admin: http://localhost/admin/

### Seeded login accounts

| Role | Email | Password (from `.env`) |
| --- | --- | --- |
| Forbmax Admin | `admin@forbmax.local` | `AdminPass123!` |
| Forbmax Member | `member@forbmax.local` | `MemberPass123!` |
| NIMAR User | `user@nimar.local` | `NimarPass123!` |

Passwords are controlled by `SEED_*_PASSWORD` in `.env`.

### Useful commands

```bash
# Follow logs
docker compose logs -f web

# Django shell
docker compose exec web python manage.py shell

# Re-run seed
docker compose exec web python manage.py seed_phase1

# Create an extra admin
docker compose exec web python manage.py createsuperuser

# Migrations (if you change models)
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
```

## Useful URLs (dev)

- Dashboard: http://localhost/
- Points: http://localhost/points/
- Kanban: http://localhost/kanban/
- Timeline: http://localhost/timeline/
- Metrics: http://localhost/metrics/
- Import (Forbmax): http://localhost/import/
- Users (Forbmax Admin): http://localhost/users/
- Export: http://localhost/api/export/excel/
- Health: http://localhost/health/

## Tests

```bash
docker compose run --rm --entrypoint pytest web
```

## Production

See `docs/DEPLOYMENT.md` and `docs/BACKUP_RESTORE.md`.

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## Phase status

Phases 1–6 complete (MVP).

## Notes

- The Excel import app is named `imports_app` to avoid clashing with Python’s import machinery.
- Free-form spreadsheet statuses (e.g. “Not implemented”) must be mapped explicitly before confirm.
- Client users only need the HTTPS URL in production — no VPN, Docker, or DB access on their side.
