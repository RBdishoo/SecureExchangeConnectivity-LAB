# Design Decisions

## Educational framing

**Decision:** Label the project as a fictional lab inspired by *public* exchange-connectivity concepts, with an explicit non-affiliation disclaimer.

**Why:** Prevents overstating any relationship to IEX (or any real exchange) while still practicing relevant security architecture skills.

## Stack

**Decision:** Python/FastAPI + PostgreSQL + Docker Compose + structured JSON logging.

**Why:** Fast to teach, easy to instrument, maps cleanly to API security / RBAC / detection coursework without requiring a full FIX stack.

## Network segmentation first

**Decision:** Four Compose networks (`edge-net`, `app-net`, `data-net`, `security-net`) before feature-rich APIs.

**Why:** Trust boundaries are harder to retrofit. Week 1 proves segmentation and telemetry; Weeks 2–4 add identity, detections, and recovery inside those boundaries.

## Internal data network

**Decision:** Mark `data-net` as `internal: true` and do not publish Postgres ports.

**Why:** Demonstrates that the database is unreachable from the lab host and from edge clients, even if the gateway is compromised in a simplistic sense (gateway is not attached to `data-net`).

## Shared logging helper

**Decision:** Centralize JSON log formatting in `services/common/logging_utils.py`.

**Why:** Consistent SIEM-ready fields (`actor_id`, `source_ip`, `action`, `result`, `correlation_id`) across services from day one.

## JWT/RBAC (Week 2)

**Decision:** Simple shared-secret JWT (HS256) with bcrypt password hashing and role claims (`member`, `security_analyst`, `operations`, `administrator`), enforced at the gateway and re-checked for tenant scope in the matching engine.

**Why:** Demonstrates authentication vs authorization and defense-in-depth without standing up Keycloak for the lab MVP.

## TLS termination (Week 2)

**Decision:** Do **not** terminate TLS inside the Compose lab services for Week 2. Document edge TLS termination instead.

**Why / how it would work in a hardened deployment:**

1. **Termination point:** A reverse proxy or load balancer (nginx, Envoy, cloud LB) on the edge terminates TLS and forwards HTTP to `gateway` on `edge-net`.
2. **Certificate lifecycle:** Issue certs from a private CA or ACME; store private keys in a secrets manager (not in git); rotate before expiry; automate renewal; revoke on compromise.
3. **Lab scope:** Compose publishes plaintext `localhost:8080` for educational demos. Enabling HTTPS locally is feasible later with a mounted self-signed cert on an nginx sidecar; it is intentionally deferred so Week 2 focuses on identity and authorization behavior.
4. **In-transit after termination:** Traffic on `app-net` / `data-net` remains private Docker networks in the lab model; production would add mTLS between services.

## Disaster recovery (Week 4)

**Decision:** Logical `pg_dump` backups with SHA-256 sidecars, restore into a Compose `--profile dr` Postgres, and verify with `verify-backup.py`. Lab targets: RPO 15 minutes, RTO 30 minutes.

**Why:** Demonstrates backup integrity and isolated restore without claiming multi-region replication. Identity/audit remain in-memory and are called out as backup gaps.

## Detection engine as Python + YAML later

**Decision:** Prefer a Python detection pipeline over standing up OpenSearch/Wazuh for the MVP.

**Why:** Keeps the lab runnable on a laptop and focuses learning on rule logic and triage, not SIEM operations.

## Placeholder secrets

**Decision:** Use clearly fake Compose credentials such as `postgres-lab-password` and `changeme-lab-only-jwt-secret`.

**Why:** Avoids accidental realism; documented in `SECURITY.md` and allowlisted narrowly in `.gitleaks.toml` for docs/compose only.
