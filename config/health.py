from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """Liveness/readiness: app process + database connectivity."""
    db_ok = False
    db_error = None
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_ok = True
    except Exception as exc:  # noqa: BLE001 - surface health failure only
        db_error = str(exc)

    payload = {
        "status": "ok" if db_ok else "degraded",
        "app": "ok",
        "database": "ok" if db_ok else "error",
    }
    if db_error and not db_ok:
        payload["database_error"] = "unavailable"

    status_code = 200 if db_ok else 503
    return JsonResponse(payload, status=status_code)
