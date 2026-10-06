# Incident Response Runbook

Educational procedures for synthetic alerts in this lab.

> Not a real SOC runbook and not affiliated with any exchange’s IR process.

## Purpose

Guide analysts through triage of synthetic security alerts and hand off to recovery when data integrity is at risk.

## Severity cheat sheet (lab)

| Level | Examples | First response |
|-------|----------|----------------|
| Critical | Privilege escalation success | Preserve audit/alerts; revert roles; rotate lab JWT secret if forged events suspected |
| High | Brute force, cross-tenant probe, order-rate anomaly | Investigate; contain actor/IP; confirm denials held |
| Medium | Suspicious source IP | Challenge/block IP; verify allowlist |

## Steps

1. **Detect** — generate or collect JSON logs (`scripts/generate-events.py` or service stdout).
2. **Alert** — run `scripts/run-detections.py`; open `data/alerts/alerts.json`.
3. **Investigate** — `scripts/investigate-alert.py` for timeline, actor, source IP, correlation IDs.
4. **Classify** — use [`detection-catalog.md`](detection-catalog.md) false-positive notes.
5. **Document** — evidence / hypothesis / conclusion ([`incident-report-cross-tenant.md`](incident-report-cross-tenant.md)).
6. **Contain** — follow alert recommendation (lab/simulated only).
7. **Recover (if DB impact)** — [`disaster-recovery-runbook.md`](disaster-recovery-runbook.md): backup → stop primary → restore DR → verify.

## Roles

| Role | IR permissions in lab |
|------|------------------------|
| `security_analyst` | Read alerts/audit; cannot change roles |
| `operations` | Health checks; backup/restore |
| `administrator` | Role changes (audited); break-glass |
| `member` | No IR tools; trading path only |
