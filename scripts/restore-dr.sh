#!/usr/bin/env bash
# Restore a lab Postgres dump into the DR profile instance (postgres-dr).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKUP_FILE="${1:-}"
if [[ -z "$BACKUP_FILE" ]]; then
  BACKUP_FILE="$(ls -1t "$ROOT"/data/backups/seclab-*.sql 2>/dev/null | head -1 || true)"
fi
if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
  echo "[restore-dr] ERROR: provide a backup .sql path (or create one with scripts/backup.sh)" >&2
  exit 1
fi

COMPOSE="${COMPOSE:-docker compose}"
USER_NAME="${POSTGRES_USER:-labuser}"
DB_NAME="${POSTGRES_DB:-seclab}"
DR_SERVICE="${DR_POSTGRES_SERVICE:-postgres-dr}"

# Elevate if needed (cloud lab VMs).
if ! $COMPOSE version >/dev/null 2>&1; then
  echo "[restore-dr] ERROR: docker compose not available" >&2
  exit 1
fi
if ! $COMPOSE ps >/dev/null 2>&1; then
  if command -v sudo >/dev/null; then
    COMPOSE="sudo docker compose"
  fi
fi

echo "[restore-dr] Starting DR Postgres profile (${DR_SERVICE})"
$COMPOSE --profile dr up -d "$DR_SERVICE"

echo "[restore-dr] Waiting for ${DR_SERVICE} healthy..."
for _ in $(seq 1 60); do
  if $COMPOSE exec -T "$DR_SERVICE" pg_isready -U "$USER_NAME" -d "$DB_NAME" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! $COMPOSE exec -T "$DR_SERVICE" pg_isready -U "$USER_NAME" -d "$DB_NAME" >/dev/null 2>&1; then
  echo "[restore-dr] ERROR: ${DR_SERVICE} not ready" >&2
  exit 1
fi

echo "[restore-dr] Restoring ${BACKUP_FILE} → ${DR_SERVICE}/${DB_NAME}"
$COMPOSE exec -T "$DR_SERVICE" psql -U "$USER_NAME" -d "$DB_NAME" -v ON_ERROR_STOP=1 <"$BACKUP_FILE"

echo "[restore-dr] OK"
echo "$BACKUP_FILE"
