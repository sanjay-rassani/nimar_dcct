# Production deployment

Shape: Internet → DNS → HTTPS/nginx → Django (gunicorn) → PostgreSQL + media volume.

NIMAR clients only need a normal HTTPS URL. No VPN, local Docker, or database credentials.

## 1. Prepare host

```bash
cp .env.example .env
# Set strong SECRET_KEY, POSTGRES_PASSWORD, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS
# DJANGO_SETTINGS_MODULE=config.settings.prod
# SEED_DEMO_DATA=0  (after first bootstrap)
```

## 2. TLS certificates

Place certs where nginx expects them:

```bash
mkdir -p certs
# fullchain.pem and privkey.pem (Let's Encrypt or corporate certs)
```

## 3. Launch

```bash
docker compose -f docker-compose.prod.yml up -d --build
curl -fk https://YOUR_HOST/health/
```

## 4. First admin

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
# or temporarily SEED_DEMO_DATA=1 on first boot, then disable
```

## 5. Backups

See `docs/BACKUP_RESTORE.md`.
