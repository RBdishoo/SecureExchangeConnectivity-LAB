# Incident Response Runbook

Educational procedures for synthetic alerts in this lab.

## Purpose

Guide analysts through triage of synthetic security alerts.

## Steps

1. Generate or collect JSON logs (`scripts/generate-events.py` or service stdout).
2. Run detections (`scripts/run-detections.py`) and open `data/alerts/alerts.json`.
3. Investigate with `scripts/investigate-alert.py` — capture timeline, actor, source IP, correlation IDs.
4. Classify using [`detection-catalog.md`](detection-catalog.md) false-positive notes.
5. Document evidence / hypothesis / conclusion (see [`incident-report-cross-tenant.md`](incident-report-cross-tenant.md)).
6. Apply recommended containment from the alert payload (lab/simulated only).
