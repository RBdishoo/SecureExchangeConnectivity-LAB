# Incident Report — Cross-Tenant Order Probe

**Lab only.** Synthetic scenario for the Secure Exchange Connectivity Lab. Not a real exchange incident.

| Field | Value |
|-------|-------|
| Incident ID | `INC-LAB-2026-XT-001` |
| Date (lab) | 2026-10-06 |
| Severity | High (educational) |
| Detection | `cross-tenant-access` |
| Status | Contained (synthetic) |
| Analyst | Lab `security_analyst` role |

---

## 1. Evidence

- Synthetic JSONL events show `usr-member-b` (`TENANT_B`) issuing `get_order` with result `denied_cross_tenant` (correlation IDs `xt-1`, `xt-2`).
- Source IP `10.0.0.22` (lab private range) — not on the suspicious-IP denylist.
- Matching-engine / gateway controls returned **403**; no order payload for `TENANT_A` appears in evidence samples.
- Related timeline (from `scripts/investigate-alert.py`) also shows nearby privilege-escalation *attempts* from the same actor family in the generated corpus — treated as separate hypotheses.

**Artifacts:** `data/logs/synthetic-events.jsonl`, alert JSON under `data/alerts/` with `rule_id=cross-tenant-access`.

---

## 2. Hypothesis

**Primary:** Member B (or automation using B’s credentials) probed another tenant’s order IDs — reconnaissance or a buggy client — without successfully reading foreign data.

**Alternate:** A shared integration test actor was mislabeled as `usr-member-b` (false positive class documented in the detection catalog).

---

## 3. Conclusion

Access **was denied** by tenant-scoped controls; impact is limited to attempted unauthorized read. Treat as a true-positive **attempt** alert for training.

**Containment / follow-up (lab):**

1. Notify the synthetic member firm contact; review recent order-ID enumeration patterns.
2. Confirm rate limits and authz tests still fail closed (`pytest` cross-tenant cases).
3. Preserve logs and alert JSON for portfolio demonstration.
4. No production systems were involved.

**Open item:** Tune detection to suppress known CI actors if this fixture is merged into automated pipelines.
