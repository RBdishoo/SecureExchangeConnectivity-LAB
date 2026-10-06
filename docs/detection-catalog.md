# Detection Catalog

Synthetic educational detections for the Secure Exchange Connectivity Lab. Rules live in [`detections/`](../detections/) as Sigma-style YAML and are evaluated by [`detections/engine.py`](../detections/engine.py).

| ID | Title | Level | Trigger (summary) |
|----|-------|-------|-------------------|
| `brute-force` | Brute Force Login Attempts | high | ≥5 `login`/`denied` for one `actor_id` in 5 minutes |
| `privilege-escalation` | Privilege Escalation / Unauthorized Role Change | critical | `change_role` elevating to `administrator`, success by non-admin, or denied admin elevation attempts |
| `cross-tenant-access` | Cross-Tenant Access Attempt | high | Order read denied as cross-tenant |
| `suspicious-source-ip` | Suspicious Source IP | medium | Auth/order activity from denylisted IP or outside private allowlist |
| `market-data-anomaly` | Order Rate Anomaly | high | ≥8 order submit attempts (ok/rate_limited/denied) per actor in 60s |

## False-positive considerations

### brute-force
- Classroom load tests that hammer a shared demo account
- Operators replaying the same denied-login fixture without resetting timestamps
- **Mitigation:** Use per-user actors; exclude `lab-setup-*` actor prefixes if added later

### privilege-escalation
- Authorized break-glass drills that grant `administrator`
- Seed/reset scripts rewriting roles during lab bootstrap
- **Mitigation:** Tag maintenance actors; require dual approval notes outside the lab

### cross-tenant-access
- Automated negative tests that intentionally request another tenant’s order
- Chatty UI retries on 403
- **Mitigation:** Deduplicate by `correlation_id`; allowlist CI test actors

### suspicious-source-ip
- Students on unexpected VPN/home IPs
- Docker bridge addresses after Compose network renumbering
- **Mitigation:** Maintain allowlist with lab VPN ranges; treat denylist hits as higher confidence

### market-data-anomaly (order-rate)
- Perf tests submitting bursts under one member
- Compressed log replay collapsing hours into one minute
- Counting both `ok` and `rate_limited` can double-count a single user retry storm (intentional for abuse visibility)
- **Mitigation:** Separate perf actor IDs; tune threshold for class size

## How to run

```bash
python scripts/generate-events.py
python scripts/run-detections.py --logs data/logs/synthetic-events.jsonl --out data/alerts
python scripts/investigate-alert.py --alert data/alerts/<alert_id>.json --logs data/logs/synthetic-events.jsonl
```
