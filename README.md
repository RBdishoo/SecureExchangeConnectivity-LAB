# Secure Exchange Connectivity Lab

A fictional, containerized exchange-connectivity environment that simulates secure member order submission, market-data distribution, role-based administration, security monitoring, and a tested disaster-recovery workflow.

> **Educational disclaimer:** This is an educational reference implementation informed by publicly available exchange-connectivity concepts. It does **not** represent IEX Group’s internal systems, configurations, security controls, or security posture.

Synthetic trading events only. No real market activity, customer data, credentials, or IEX systems are used.

## Setup

```bash
docker compose up --build
./scripts/health-check.sh
```

Gateway (only host-published service): `http://localhost:8080`

Tests:

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Lab users (synthetic — local demos only)

| Username | Password | Role | Tenant |
|----------|----------|------|--------|
| `member_a` | `MemberA1!` | member | TENANT_A |
| `member_b` | `MemberB1!` | member | TENANT_B |
| `analyst` | `Analyst1!` | security_analyst | — |
| `ops` | `OpsUser1!` | operations | LAB |
| `admin` | `Admin1!lab` | administrator | LAB |

## End-to-end demo script

Covers: **valid order → blocked cross-tenant → trigger alert → investigate → restore backup**.

```bash
# 0) Stack up
docker compose up --build -d
./scripts/health-check.sh

# 1) Valid order (member A)
TOKEN_A=$(curl -s -X POST http://localhost:8080/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"member_a","password":"MemberA1!"}' | jq -r .access_token)
ORDER=$(curl -s -X POST http://localhost:8080/orders \
  -H "authorization: Bearer $TOKEN_A" \
  -H 'content-type: application/json' \
  -d '{"symbol":"SYNTH","side":"buy","quantity":5,"price":"10.25","client_order_id":"demo-1"}')
echo "$ORDER" | jq
ORDER_ID=$(echo "$ORDER" | jq -r .order_id)

# 2) Blocked cross-tenant read (member B → A's order) — expect HTTP 403
TOKEN_B=$(curl -s -X POST http://localhost:8080/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"member_b","password":"MemberB1!"}' | jq -r .access_token)
curl -s -o /dev/stderr -w "cross_tenant_status=%{http_code}\n" \
  -H "authorization: Bearer $TOKEN_B" \
  "http://localhost:8080/orders/$ORDER_ID"

# 3) Trigger alerts from synthetic malicious + benign corpus
python scripts/generate-events.py --out data/logs/synthetic-events.jsonl
python scripts/run-detections.py --logs data/logs/synthetic-events.jsonl --out data/alerts
python -c 'import json; print("rules", sorted({a["rule_id"] for a in json.load(open("data/alerts/alerts.json"))}))'

# 4) Investigate (prefer a cross-tenant alert when present)
ALERT=$(python -c 'import json; a=json.load(open("data/alerts/alerts.json")); print(next(x["alert_id"] for x in a if x["rule_id"]=="cross-tenant-access"))')
python scripts/investigate-alert.py \
  --alert "data/alerts/$ALERT.json" \
  --logs data/logs/synthetic-events.jsonl

# 5) Backup → simulate primary DB stop → restore DR → verify
./scripts/backup.sh
BACKUP=$(ls -1t data/backups/seclab-*.sql | head -1)
docker compose stop postgres
./scripts/restore-dr.sh "$BACKUP"
python scripts/verify-backup.py --backup "$BACKUP" --check-dr --min-orders 1 \
  --out docs/assets/verify-backup-report.json
docker compose start postgres   # recover primary when demo ends
```

Optional video: skip unless you want a local screen recording — the script above is the portfolio demo path. Captured DR evidence: [`docs/assets/dr-simulation.md`](docs/assets/dr-simulation.md).

## Services and trust boundaries

| Service | Purpose | Networks | Trust boundary |
|---------|---------|----------|----------------|
| **gateway** | Edge entry; JWT auth; orders; rate limits | `edge-net`, `app-net`, `security-net` | Terminates untrusted member/lab traffic; only published port (`:8080`) |
| **identity** | Login, bcrypt, JWT, RBAC, audit | `app-net` | Not internet-reachable |
| **matching-engine** | Tenant-scoped synthetic orders | `app-net`, `data-net` | Only app service on the data plane |
| **market-data** | Health scaffold | `app-net` | App-plane stub |
| **alerting** | Detection engine API | `security-net` | Monitoring plane |
| **postgres** | Primary lab DB | `data-net` (**internal**) | No host port |
| **postgres-dr** | DR DB (`--profile dr`) | `data-net` | Started only for recovery drills |

## Security decisions (short)

- Segment networks before features; keep Postgres off the host network namespace.
- Prefer JWT/RBAC + tenant checks over “successful HTTP” as the security story.
- Emit SIEM-ready JSON logs from day one; detect with portable YAML + Python.
- Document TLS edge termination rather than fake HTTPS inside Compose.
- Prove recovery with checksummed logical dumps and an isolated DR profile (RPO 15m / RTO 30m lab targets).

Details: [`docs/security-architecture-summary.md`](docs/security-architecture-summary.md) · [`docs/design-decisions.md`](docs/design-decisions.md)

## Documentation

| Doc | Description |
|-----|-------------|
| [`docs/architecture.md`](docs/architecture.md) | System overview |
| [`docs/security-architecture-summary.md`](docs/security-architecture-summary.md) | One-page control map |
| [`docs/threat-model.md`](docs/threat-model.md) | Order / role / investigate / DR threats |
| [`docs/trust-boundaries.md`](docs/trust-boundaries.md) | Zone rules |
| [`docs/data-flow.md`](docs/data-flow.md) | Request and log flows |
| [`docs/detection-catalog.md`](docs/detection-catalog.md) | Detections + false positives |
| [`docs/incident-response-runbook.md`](docs/incident-response-runbook.md) | Triage steps |
| [`docs/incident-report-cross-tenant.md`](docs/incident-report-cross-tenant.md) | Sample investigation |
| [`docs/disaster-recovery-runbook.md`](docs/disaster-recovery-runbook.md) | Backup / restore / RPO-RTO |
| [`diagrams/`](diagrams/) | Mermaid sources (render on GitHub) |

## Status / Definition of Done

- Weeks 1–4 complete for this lab scope.
- Documented setup (`docker compose up --build`)
- No real secrets committed (lab placeholders + Gitleaks config/CI)
- ≥25 automated tests (see `pytest`)
- Five detections with repeatable triggers
- Written investigation + DR restore verification evidence
- Architecture / data-flow / recovery diagrams included
- README covers setup, demo, security decisions, limitations, disclaimer

## Limitations

- No real FIX sessions, market data feeds, or exchange connectivity.
- TLS is not terminated in Compose (edge-termination model documented).
- Identity user store and audit log are in-memory (not covered by Postgres backups).
- Matching-engine also keeps an in-memory cache; durable demo state is what was persisted to Postgres.
- Detections use offline JSONL (not a full SIEM); thresholds are lab-tuned.
- Logical `pg_dump` only — not continuous replication / WAL shipping.
- Compose credentials / JWT secret are lab placeholders — never reuse outside this repo.
- Network isolation here is a Docker Compose teaching model, not a production VPC/multi-region design.

## License

MIT — see [`LICENSE`](LICENSE). Security reporting: [`SECURITY.md`](SECURITY.md). Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md).
