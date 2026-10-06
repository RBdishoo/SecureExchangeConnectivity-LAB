# Threat Model

## Scope

Threat model for the Secure Exchange Connectivity Lab (synthetic educational environment).

> Not a model of any real exchange. Assets, actors, and controls below are lab constructs.

## Assets

| Asset | Sensitivity | Notes |
|-------|-------------|-------|
| Synthetic order messages | Medium (lab) | Mock only; still treat as tenant-scoped |
| Identity / role assignments | High | Admin changes are privileged |
| PostgreSQL lab database | High | data-net only; backup/DR artifacts |
| Structured security logs | Medium | May contain actor IDs; no tokens |
| Alerting pipeline | Medium | Lives on security-net |
| Backup dumps | High (lab) | Same sensitivity as DB; store under `data/backups/` (gitignored) |

## Actors

| Actor | Trust | Capabilities (intended) |
|-------|-------|-------------------------|
| Member | Low | Submit/read own-tenant synthetic orders via gateway |
| Security analyst | Medium | Investigate alerts; read audit; cannot change roles |
| Operations | Medium | Health, backup/restore |
| Administrator | High | Role changes (audited) |
| External attacker | None | Probe exposed edge; attempt lateral movement / cross-tenant reads |

## Scenarios

### 1. Member submits an order

| | |
|--|--|
| **Flow** | Member → gateway → JWT/RBAC → matching-engine → PostgreSQL |
| **Threats** | Spoofed identity, cross-tenant order, injection, replay, order-rate abuse |
| **Controls** | Network segmentation; JWT; schema validation; rate limits; structured logs; order-rate detection |

### 2. Administrator changes a user role

| | |
|--|--|
| **Flow** | Admin → gateway → identity |
| **Threats** | Privilege escalation, unauthorized role change, missing audit trail |
| **Controls** | Admin-only RBAC; append-only audit; privilege-escalation detection |

### 3. Analyst investigates an alert

| | |
|--|--|
| **Flow** | Analyst → tooling → alerting / logs |
| **Threats** | Over-privileged access, log tampering, alert noise |
| **Controls** | Analyst cannot modify roles; investigate script; detection catalog FP notes |

### 4. DR restoration occurs

| | |
|--|--|
| **Flow** | Ops backs up Postgres → outage → restore to `postgres-dr` → verify |
| **Threats** | Corrupt/incomplete backup, restore to wrong environment, secret leakage in backup media |
| **Controls** | SHA-256 sidecars; verify script; internal data-net; gitignore backups; RPO/RTO documented |

## STRIDE snapshot (edge gateway)

| Category | Example | Mitigation direction |
|----------|---------|----------------------|
| Spoofing | Fake member credentials | JWT + hashed passwords |
| Tampering | Altered order payload | Validation + integrity checks |
| Repudiation | Denied admin action | Audit logs with actor + correlation ID |
| Information disclosure | DB exposed to host | data-net internal; no host port |
| Denial of service | Flood gateway | Rate limits + order-rate detection |
| Elevation of privilege | Member → admin role | RBAC + privilege-escalation detection |
