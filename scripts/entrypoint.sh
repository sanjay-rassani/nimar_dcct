#!/bin/sh
set -e

echo "Waiting for database..."
python <<'PY'
import os
import time
import sys

import psycopg

url = os.environ.get("DATABASE_URL", "")
if not url:
    print("DATABASE_URL is not set", file=sys.stderr)
    sys.exit(1)

# psycopg accepts postgres:// and postgresql://
dsn = url.replace("postgres://", "postgresql://", 1)

for attempt in range(30):
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        print("Database is ready.")
        break
    except Exception as exc:
        print(f"DB not ready ({attempt + 1}/30): {exc}")
        time.sleep(1)
else:
    print("Database did not become ready in time.", file=sys.stderr)
    sys.exit(1)
PY

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

if [ "${SEED_DEMO_DATA:-1}" = "1" ]; then
  echo "Seeding demo data..."
  python manage.py seed_phase1
fi

echo "Starting application..."
exec "$@"
