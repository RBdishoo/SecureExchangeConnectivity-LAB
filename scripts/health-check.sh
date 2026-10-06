#!/usr/bin/env bash
# Lab health check across gateway and core containers.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE="${COMPOSE:-docker compose}"
if ! $COMPOSE ps >/dev/null 2>&1; then
  if command -v sudo >/dev/null && sudo docker compose ps >/dev/null 2>&1; then
    COMPOSE="sudo docker compose"
  fi
fi

fail=0

echo "[health] Gateway (host :8080)"
if curl -sf "http://localhost:8080/health" >/tmp/secx-gw-health.json; then
  cat /tmp/secx-gw-health.json
  echo
else
  echo "[health] FAIL gateway"
  fail=1
fi

echo "[health] Compose services"
$COMPOSE ps || fail=1

for svc in identity matching-engine market-data alerting postgres; do
  echo "[health] ${svc}"
  if $COMPOSE exec -T "$svc" true >/dev/null 2>&1; then
    echo "  container reachable"
  else
    echo "  FAIL: container not reachable"
    fail=1
  fi
done

if $COMPOSE exec -T postgres pg_isready -U labuser -d seclab >/dev/null 2>&1; then
  echo "[health] postgres: ready"
else
  echo "[health] FAIL postgres not ready"
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  echo "[health] FAILED"
  exit 1
fi
echo "[health] OK"
