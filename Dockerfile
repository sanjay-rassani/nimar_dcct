# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN chmod +x /app/scripts/entrypoint.sh \
    && mkdir -p /app/staticfiles /app/media

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]

FROM base AS development
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS production
# Keep root for entrypoint (migrate/collectstatic on mounted volumes), then drop via gunicorn --user.
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--user", "appuser", "--group", "appuser"]
