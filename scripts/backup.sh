#!/usr/bin/env bash
# Logical backup of the lab primary Postgres (pg_dump).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT_DIR="${1:-$ROOT/data/backups}"
COMPOSE="${COMPOSE:-docker compose}"
SERVICE="${POSTGRES_SERVICE:-postgres}"
USER_NAME="${POSTGRES_USER:-labuser}"
DB_NAME="${POSTGRES_DB:-seclab}"

mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$OUT_DIR/seclab-${STAMP}.sql"

echo "[backup] Dumping ${SERVICE}/${DB_NAME} → ${OUT_FILE}"
# Prefer sudo docker when the daemon requires elevated access in lab VMs.
if ! $COMPOSE exec -T "$SERVICE" pg_isready -U "$USER_NAME" -d "$DB_NAME" >/dev/null 2>&1; then
  if command -v sudo >/dev/null && sudo docker compose exec -T "$SERVICE" pg_isready -U "$USER_NAME" -d "$DB_NAME" >/dev/null 2>&1; then
    COMPOSE="sudo docker compose"
  else
    echo "[backup] ERROR: Postgres service '${SERVICE}' is not ready" >&2
    exit 1
  fi
fi

$COMPOSE exec -T "$SERVICE" pg_dump -U "$USER_NAME" -d "$DB_NAME" --clean --if-exists --no-owner >"$OUT_FILE"

if [[ ! -s "$OUT_FILE" ]]; then
  echo "[backup] ERROR: dump file is empty" >&2
  exit 1
fi

if command -v sha256sum >/dev/null; then
  sha256sum "$OUT_FILE" | tee "${OUT_FILE}.sha256"
else
  shasum -a 256 "$OUT_FILE" | tee "${OUT_FILE}.sha256"
fi

# Manifest for verify-backup / DR reporting
OUT_FILE="$OUT_FILE" STAMP="$STAMP" DB_NAME="$DB_NAME" SERVICE="$SERVICE" python3 - <<'PY'
import json, os, pathlib, re
out = pathlib.Path(os.environ["OUT_FILE"])
text = out.read_text(encoding="utf-8", errors="replace")
manifest = {
    "backup_file": str(out),
    "bytes": out.stat().st_size,
    "created_at_utc": os.environ["STAMP"],
    "database": os.environ["DB_NAME"],
    "service": os.environ["SERVICE"],
    "sha256_file": str(out) + ".sha256",
    "contains_orders_table": "CREATE TABLE" in text and "orders" in text,
    "insert_hint_count": len(re.findall(r"^INSERT INTO", text, flags=re.M)),
}
path = out.with_suffix(out.suffix + ".manifest.json")
path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"[backup] Manifest → {path}")
print(json.dumps(manifest, indent=2))
PY

echo "[backup] OK: $OUT_FILE"
echo "$OUT_FILE"
