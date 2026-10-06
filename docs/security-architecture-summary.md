# Security Architecture Summary

One-page view of the Secure Exchange Connectivity Lab security design (educational / synthetic).

> This lab is informed by publicly available exchange-connectivity concepts. It does **not** represent IEX Group’s internal systems, configurations, security controls, or security posture.

## Control map

| Concern | Lab control |
|---------|-------------|
| Edge exposure | Only `gateway` publishes a host port (`:8080`) |
| Network segmentation | `edge-net` / `app-net` / `data-net` (internal) / `security-net` |
| Authentication | bcrypt password hashes + expiring JWT (HS256) |
| Authorization | RBAC roles + tenant-scoped order access |
| Admin accountability | Append-only role-change audit records |
| Protocol hygiene | Order schema validation, body size limit, member rate limit |
| Telemetry | Structured JSON logs (`actor_id`, `source_ip`, `action`, `result`, `correlation_id`) |
| Detection | Five Sigma-style YAML rules + Python matcher |
| Triage | `investigate-alert.py` + written incident report |
| Vulnerability workflow | GitHub Actions: Gitleaks, Semgrep, pip-audit, Trivy |
| Resilience | `pg_dump` backup → DR Postgres profile → verify checksum/rows |
| TLS | Edge termination documented (not enabled in Compose) |

## Trust boundaries (short)

1. Untrusted clients → gateway (`edge-net`)
2. Gateway → identity / matching / market-data (`app-net`)
3. Matching → Postgres only (`data-net`)
4. Alerting on `security-net`

## Demo narrative

Valid member order → blocked cross-tenant read → generate/detect alert → investigate → backup/restore after simulated DB stop.

See README **End-to-end demo script** and [`disaster-recovery-runbook.md`](disaster-recovery-runbook.md).
