# Secure Exchange Connectivity Lab

A fictional, containerized exchange-connectivity environment that simulates secure member order submission, market-data distribution, role-based administration, security monitoring, and a tested disaster-recovery workflow.

> **Educational disclaimer:** This is an educational reference implementation informed by publicly available exchange-connectivity concepts. It does not represent IEX Group’s internal systems, configurations, security controls, or security posture.

Synthetic trading events only. No real market activity, customer data, credentials, or IEX systems are used.

## Quick start

```bash
docker compose up --build
```

Gateway health (only host-exposed service):

```bash
curl -s http://localhost:8080/health | jq
```

### Auth demo (Week 2)

Lab users (synthetic passwords — local demos only):

| Username | Password | Role | Tenant |
|----------|----------|------|--------|
| `member_a` | `MemberA1!` | member | TENANT_A |
| `member_b` | `MemberB1!` | member | TENANT_B |
| `analyst` | `Analyst1!` | security_analyst | — |
| `ops` | `OpsUser1!` | operations | LAB |
| `admin` | `Admin1!lab` | administrator | LAB |

```bash
# Login as member A and submit an order
TOKEN_A=$(curl -s -X POST http://localhost:8080/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"member_a","password":"MemberA1!"}' | jq -r .access_token)

ORDER=$(curl -s -X POST http://localhost:8080/orders \
  -H "authorization: Bearer $TOKEN_A" \
  -H 'content-type: application/json' \
  -d '{"symbol":"SYNTH","side":"buy","quantity":5,"price":"10.25","client_order_id":"demo-1"}')
echo "$ORDER" | jq
ORDER_ID=$(echo "$ORDER" | jq -r .order_id)

# Cross-tenant read blocked (member B → A's order)
TOKEN_B=$(curl -s -X POST http://localhost:8080/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"member_b","password":"MemberB1!"}' | jq -r .access_token)
curl -s -o /dev/stderr -w "%{http_code}\n" \
  -H "authorization: Bearer $TOKEN_B" \
  http://localhost:8080/orders/$ORDER_ID

# Analyst cannot modify roles (expect 403)
TOKEN_AN=$(curl -s -X POST http://localhost:8080/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"analyst","password":"Analyst1!"}' | jq -r .access_token)
curl -s -o /dev/stderr -w "%{http_code}\n" -X PATCH \
  -H "authorization: Bearer $TOKEN_AN" \
  -H 'content-type: application/json' \
  -d '{"role":"administrator"}' \
  http://localhost:8080/users/usr-member-a/role

# Admin role change creates audit record
TOKEN_ADMIN=$(curl -s -X POST http://localhost:8080/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"Admin1!lab"}' | jq -r .access_token)
curl -s -X PATCH http://localhost:8080/users/usr-ops/role \
  -H "authorization: Bearer $TOKEN_ADMIN" \
  -H 'content-type: application/json' \
  -d '{"role":"security_analyst"}' | jq .audit
curl -s -H "authorization: Bearer $TOKEN_ADMIN" http://localhost:8080/audit | jq '.audit[-1]'
```

### Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Inspect structured JSON logs:

```bash
docker compose logs gateway --tail=20
docker compose logs identity --tail=20
docker compose logs matching-engine --tail=20
```

Stop:

```bash
docker compose down
```

## Services and trust boundaries

| Service | Purpose | Networks | Trust boundary |
|---------|---------|----------|----------------|
| **gateway** | Edge entry; JWT auth; orders; rate limits | `edge-net`, `app-net`, `security-net` | Terminates untrusted member/lab traffic; only published port (`:8080`) |
| **identity** | Login, bcrypt passwords, JWT, RBAC, audit | `app-net` | Not internet-reachable; auth decisions stay on the app plane |
| **matching-engine** | Tenant-scoped synthetic orders | `app-net`, `data-net` | Only app service allowed onto the data plane |
| **market-data** | `/health` scaffold | `app-net` | App-plane distribution stub |
| **alerting** | `/health` scaffold | `security-net` | Monitoring plane separated from trading path |
| **postgres** | Lab database | `data-net` (**internal**) | No host port; unreachable from edge |

Network diagram: [`diagrams/network-zones.mmd`](diagrams/network-zones.mmd) · Trust boundaries: [`docs/trust-boundaries.md`](docs/trust-boundaries.md)

## Structured logging

Every service emits JSON lines including:

- `timestamp`
- `actor_id`
- `source_ip`
- `action`
- `result`
- `correlation_id`

Pass optional headers on requests: `x-actor-id`, `x-correlation-id`.

## Documentation

| Doc | Description |
|-----|-------------|
| [`docs/architecture.md`](docs/architecture.md) | System overview |
| [`docs/threat-model.md`](docs/threat-model.md) | Threats for order, role change, investigate, DR |
| [`docs/trust-boundaries.md`](docs/trust-boundaries.md) | Zone rules |
| [`docs/data-flow.md`](docs/data-flow.md) | Request and log flows |
| [`docs/design-decisions.md`](docs/design-decisions.md) | Why this stack and shape (incl. TLS termination) |
| [`diagrams/`](diagrams/) | Mermaid sources (render on GitHub) |

## Status

- **Week 1 complete:** Compose networks, health services, JSON logging, docs/diagrams.
- **Week 2 complete:** JWT/RBAC, tenant-scoped orders, admin audit, validation, rate limits, negative tests.
- Later: detections/triage/CI (3), backup/DR + portfolio polish (4).

## Limitations

- No real FIX sessions, market data feeds, or exchange connectivity.
- TLS is **not** terminated in Compose; see design-decisions for edge-termination + cert lifecycle.
- Identity user store and audit log are in-memory (reset on container restart).
- Matching engine enforces tenancy in-process; Postgres persistence is best-effort.
- Detections, backups, and security CI remain stubs/scaffolds.
- Compose credentials / JWT secret are lab placeholders — never reuse outside this repo.
- `data-net` isolation is a Docker Compose teaching model, not a production VPC design.

## License

MIT — see [`LICENSE`](LICENSE). Security reporting: [`SECURITY.md`](SECURITY.md). Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md).
