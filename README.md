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

| Service | Purpose (Week 1) | Networks | Trust boundary |
|---------|------------------|----------|----------------|
| **gateway** | Edge entry; `/health` | `edge-net`, `app-net`, `security-net` | Terminates untrusted member/lab traffic; only published port (`:8080`) |
| **identity** | `/health`, `/roles` scaffold | `app-net` | Not internet-reachable; auth decisions stay on the app plane |
| **matching-engine** | `/health`; DB URL configured | `app-net`, `data-net` | Only app service allowed onto the data plane |
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
| [`docs/design-decisions.md`](docs/design-decisions.md) | Why this stack and shape |
| [`diagrams/`](diagrams/) | Mermaid sources (render on GitHub) |

## Week 1 status

Complete: Compose networks, minimal FastAPI health services, JSON logging, architecture docs/diagrams.

Later weeks: JWT/RBAC (2), detections/triage/CI (3), backup/DR + portfolio polish (4).

## Limitations

- No real FIX sessions, market data feeds, or exchange connectivity.
- Authentication and authorization are **not** enforced yet (Week 2).
- Detections, backups, and security CI are stubs/scaffolds.
- Compose credentials are lab placeholders (`postgres-lab-password`) — never reuse outside this repo.
- `data-net` isolation is a Docker Compose teaching model, not a production VPC design.

## License

MIT — see [`LICENSE`](LICENSE). Security reporting: [`SECURITY.md`](SECURITY.md). Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md).
