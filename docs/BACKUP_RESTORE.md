# Production backup & restore

## What is backed up

- PostgreSQL dump (`backup` service → `/backups/db/*.sql.gz`)
- Evidence/media volume (`/backups/media/*.tar.gz`)
- Default retention: 14 days (`BACKUP_RETENTION_DAYS`)

## Daily backups (production Compose)

```bash
docker compose -f docker-compose.prod.yml up -d backup
docker compose -f docker-compose.prod.yml logs -f backup
```

The sidecar runs `scripts/backup.sh` once per day inside the Compose network.

## Manual backup now

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "nimar_manual_$(date -u +%Y%m%d).sql.gz"

docker compose -f docker-compose.prod.yml run --rm --no-deps \
  -v "$(pwd)/manual_media:/out" backup \
  tar -czf /out/media_manual.tar.gz -C /app/media .
```

## Restore procedure (tested shape)

1. Stop web traffic:
   ```bash
   docker compose -f docker-compose.prod.yml stop nginx web
   ```
2. Restore database (destroys current data in target DB):
   ```bash
   gunzip -c nimar_dcct_YYYYMMDD.sql.gz | \
     docker compose -f docker-compose.prod.yml exec -T db \
     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
   ```
3. Restore media:
   ```bash
   docker compose -f docker-compose.prod.yml run --rm --no-deps \
     -v "$(pwd):/restore:ro" web \
     sh -c 'rm -rf /app/media/* && tar -xzf /restore/media_YYYYMMDD.tar.gz -C /app/media'
   ```
   Or copy into the `media_data` volume with a temporary alpine container.
4. Start services and verify:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   curl -fk https://YOUR_HOST/health/
   ```

## Local/dev note

Dev Compose does not run the backup sidecar. Production uses `docker-compose.prod.yml` only for HTTPS + backups.
