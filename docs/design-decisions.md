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

## JWT/RBAC deferred to Week 2

**Decision:** Identity exposes `/health` and `/roles` only in Week 1.

**Why:** Establishes the service and network placement first; authorization logic arrives with negative tests in Week 2.

## Detection engine as Python + YAML later

**Decision:** Prefer a Python detection pipeline over standing up OpenSearch/Wazuh for the MVP.

**Why:** Keeps the lab runnable on a laptop and focuses learning on rule logic and triage, not SIEM operations.

## Placeholder secrets

**Decision:** Use clearly fake Compose credentials such as `postgres-lab-password`.

**Why:** Avoids accidental realism; documented in `SECURITY.md` and allowlisted narrowly in `.gitleaks.toml` for docs/compose only.
