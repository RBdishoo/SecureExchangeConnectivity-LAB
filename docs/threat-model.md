# Threat Model

## Scope

Week 1 threat model for the Secure Exchange Connectivity Lab (synthetic educational environment).

> Not a model of any real exchange. Assets, actors, and controls below are lab constructs.

## Assets

| Asset | Sensitivity | Notes |
|-------|-------------|-------|
| Synthetic order messages | Medium (lab) | Mock only; still treat as tenant-scoped |
| Identity / role assignments | High | Admin changes are privileged |
| PostgreSQL lab database | High | data-net only |
| Structured security logs | Medium | May contain actor IDs; no tokens |
| Alerting pipeline (future) | Medium | Lives on security-net |

## Actors

| Actor | Trust | Capabilities (intended) |
|-------|-------|-------------------------|
| Member | Low | Submit synthetic orders via gateway (Week 2+) |
| Security analyst | Medium | Investigate alerts (Week 3+) |
| Operations | Medium | Health, backup/restore (Week 4+) |
| Administrator | High | Role changes (Week 2+) |
| External attacker | None | Probe exposed edge; attempt lateral movement |

## Scenarios

### 1. Member submits an order

| | |
|--|--|
| **Flow** | Member → gateway → identity (authz) → matching-engine → PostgreSQL |
| **Threats** | Spoofed identity, cross-tenant order, injection, replay, order-rate abuse |
| **Week 1 controls** | Network segmentation; structured request logs with correlation IDs |
| **Later controls** | JWT/RBAC, validation, rate limits, detections |

### 2. Administrator changes a user role

| | |
|--|--|
| **Flow** | Admin → gateway → identity |
| **Threats** | Privilege escalation, unauthorized role change, missing audit trail |
| **Week 1 controls** | Identity service isolated to app-net; logging scaffold |
| **Later controls** | RBAC on admin APIs; immutable admin-action audit events; privilege-escalation detection |

### 3. Analyst investigates an alert

| | |
|--|--|
| **Flow** | Analyst → gateway / tooling → alerting (+ log access) |
| **Threats** | Over-privileged analyst access, log tampering, alert noise hiding real events |
| **Week 1 controls** | Alerting on security-net; JSON logs ready for triage |
| **Later controls** | Least-privilege analyst role; investigate scripts; detection catalog |

### 4. DR restoration occurs

| | |
|--|--|
| **Flow** | Operations restores backup into DR Postgres; verify integrity |
| **Threats** | Corrupt/incomplete backup, restore to wrong environment, secret leakage in backup media |
| **Week 1 controls** | Postgres confined to internal data-net; documented recovery stub diagram |
| **Later controls** | `backup.sh` / `restore-dr.sh`, integrity verification, runbooks |

## STRIDE snapshot (edge gateway)

| Category | Example | Mitigation direction |
|----------|---------|----------------------|
| Spoofing | Fake member credentials | JWT + hashed passwords (Week 2) |
| Tampering | Altered order payload | Validation + integrity checks |
| Repudiation | Denied admin action | Audit logs with actor + correlation ID |
| Information disclosure | DB exposed to host | data-net internal; no host port |
| Denial of service | Flood gateway | Rate limits (Week 2) |
| Elevation of privilege | Member → admin role | RBAC + detection (Weeks 2–3) |
