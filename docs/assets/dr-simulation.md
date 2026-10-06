# DR simulation evidence (lab)

Captured during Week 4 portfolio drill. Synthetic data only.

```text
=== health-check ===
[health] Gateway (host :8080)
{"status":"ok","service":"gateway","zone":"edge","message":"Synthetic educational gateway health endpoint","auth":"enabled"}
[health] Compose services
NAME                   IMAGE                       COMMAND                  SERVICE           CREATED          STATUS                    PORTS
secx-alerting          workspace-alerting          "uvicorn main:app --…"   alerting          2 minutes ago    Up 2 minutes (healthy)    8004/tcp
secx-gateway           workspace-gateway           "uvicorn main:app --…"   gateway           8 minutes ago    Up 8 minutes (healthy)    0.0.0.0:8080->8000/tcp, [::]:8080->8000/tcp
secx-identity          workspace-identity          "uvicorn main:app --…"   identity          8 minutes ago    Up 8 minutes (healthy)    8001/tcp
secx-market-data       workspace-market-data       "uvicorn main:app --…"   market-data       8 minutes ago    Up 8 minutes (healthy)    8003/tcp
secx-matching-engine   workspace-matching-engine   "uvicorn main:app --…"   matching-engine   8 minutes ago    Up 8 minutes (healthy)    8002/tcp
secx-postgres          postgres:16-alpine          "docker-entrypoint.s…"   postgres          21 minutes ago   Up 21 minutes (healthy)   5432/tcp
[health] identity
  container reachable
[health] matching-engine
  container reachable
[health] market-data
  container reachable
[health] alerting
  container reachable
[health] postgres
  container reachable
[health] postgres: ready
[health] OK

=== submit synthetic order for durable rows ===
{"order_id":"e8698eed-0ff6-4418-aaa5-295a45bd7173","tenant_id":"TENANT_A","owner_user_id":"usr-member-a","symbol":"SYNTH","side":"buy","quantity":5,"price":"10.25","client_order_id":"dr-demo-1","status":"accepted","created_at":"2026-10-06T19:10:25.701712+00:00"}

=== primary orders count ===
2

=== backup ===
[backup] Dumping postgres/seclab → /workspace/data/backups/seclab-20261006T191025Z.sql
dd4ca04dabe297f90286e92ab4770f8dbc301df0c6d132e9fd18c7a5bdec5812  /workspace/data/backups/seclab-20261006T191025Z.sql
[backup] Manifest → /workspace/data/backups/seclab-20261006T191025Z.sql.manifest.json
{
  "backup_file": "/workspace/data/backups/seclab-20261006T191025Z.sql",
  "bytes": 1868,
  "created_at_utc": "20261006T191025Z",
  "database": "seclab",
  "service": "postgres",
  "sha256_file": "/workspace/data/backups/seclab-20261006T191025Z.sql.sha256",
  "contains_orders_table": true,
  "insert_hint_count": 0
}
[backup] OK: /workspace/data/backups/seclab-20261006T191025Z.sql
/workspace/data/backups/seclab-20261006T191025Z.sql

=== stop primary postgres (simulated outage) ===
NAME      IMAGE     COMMAND   SERVICE   CREATED   STATUS    PORTS

=== restore into DR profile ===
[restore-dr] Starting DR Postgres profile (postgres-dr)
[restore-dr] Waiting for postgres-dr healthy...
[restore-dr] Restoring /workspace/data/backups/seclab-20261006T191025Z.sql → postgres-dr/seclab
SET
SET
SET
SET
SET
 set_config 
------------
 
(1 row)

SET
SET
SET
SET
ALTER TABLE
DROP TABLE
SET
SET
CREATE TABLE
COPY 2
ALTER TABLE
[restore-dr] OK
/workspace/data/backups/seclab-20261006T191025Z.sql

=== verify backup + DR row count ===
{
  "backup_file": "/workspace/data/backups/seclab-20261006T191025Z.sql",
  "sha256": "dd4ca04dabe297f90286e92ab4770f8dbc301df0c6d132e9fd18c7a5bdec5812",
  "sha256_match": true,
  "expected_sha256": "dd4ca04dabe297f90286e92ab4770f8dbc301df0c6d132e9fd18c7a5bdec5812",
  "bytes": 1868,
  "non_empty": true,
  "has_orders_ddl": true,
  "copy_or_insert_orders": true,
  "insert_statements": 0,
  "dr_orders_count": 2,
  "ok": true
}

=== restart primary ===
/var/run/postgresql:5432 - accepting connections
```

## Notes

- Lab RPO target: 15 minutes; RTO target: 30 minutes (see disaster-recovery-runbook).
- Backup artifact path: `/workspace/data/backups/seclab-20261006T191025Z.sql` (gitignored; checksum sidecar alongside).
- Machine-readable verify report: [verify-backup-report.json](verify-backup-report.json).
