# Disaster Recovery Runbook

Educational DR procedures for the Secure Exchange Connectivity Lab (synthetic data only).

> **Disclaimer:** This does not represent any real exchange’s recovery architecture.

## Objectives (lab targets)

| Metric | Lab target | Meaning in this project |
|--------|------------|-------------------------|
| **RPO** | **15 minutes** | At most ~15 minutes of synthetic order data may be lost if the last backup is that old |
| **RTO** | **30 minutes** | A verified DR Postgres should be available within ~30 minutes of declaring a lab outage |

These targets are teaching values for portfolio discussion — not contractual SLOs.

## Components

| Piece | Role |
|-------|------|
| `postgres` | Primary lab database on internal `data-net` |
| `postgres-dr` | DR instance (`docker compose --profile dr`) on `data-net` |
| `scripts/backup.sh` | `pg_dump` + SHA-256 + manifest |
| `scripts/restore-dr.sh` | Restore dump into `postgres-dr` |
| `scripts/verify-backup.py` | Checksum + dump structure + optional DR row counts |
| `scripts/health-check.sh` | Gateway + container readiness |

Diagram: [`diagrams/recovery-flow.mmd`](../diagrams/recovery-flow.mmd)

## Backup (steady state)

```bash
docker compose up -d
# Ensure at least one synthetic order has been persisted (see README demo)
./scripts/backup.sh
# → data/backups/seclab-<UTC>.sql (+ .sha256 + .manifest.json)
```

**Cadence (lab):** take a backup at least every 15 minutes during demos to stay inside the RPO story.

## Restore into DR

```bash
./scripts/restore-dr.sh data/backups/seclab-<UTC>.sql
python scripts/verify-backup.py --backup data/backups/seclab-<UTC>.sql --check-dr --min-orders 1 \
  --out docs/assets/verify-backup-report.json
```

## Simulated primary outage

1. Confirm primary healthy: `./scripts/health-check.sh`
2. Take a fresh backup: `./scripts/backup.sh`
3. Stop primary DB: `docker compose stop postgres`
4. Start/restore DR: `./scripts/restore-dr.sh <backup.sql>`
5. Verify: `python scripts/verify-backup.py --backup <backup.sql> --check-dr --min-orders 1`
6. Record evidence under `docs/assets/`
7. Bring primary back when finished: `docker compose start postgres`

Evidence from the portfolio simulation: [`docs/assets/dr-simulation.md`](assets/dr-simulation.md)

## Integrity checks

`verify-backup.py` confirms:

- Dump is non-empty
- SHA-256 matches sidecar (when present)
- `orders` table DDL is present
- Optionally, `postgres-dr` `SELECT COUNT(*) FROM orders` meets `--min-orders`

## Limitations

- Logical dumps only (not continuous WAL shipping)
- Identity/audit state is in-memory and **not** in Postgres backups
- Matching-engine memory cache is not restored — DB is the durable order store for this lab
- `data-net` isolation is a Compose teaching model, not a multi-region cloud design
