#!/usr/bin/env python3
"""Generate benign and malicious synthetic JSONL security/trading events."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ts(base: datetime, seconds: float) -> str:
    return (base + timedelta(seconds=seconds)).isoformat()


def _event(
    *,
    base: datetime,
    offset: float,
    action: str,
    result: str,
    actor_id: str,
    source_ip: str,
    correlation_id: str | None = None,
    **extra,
) -> dict:
    payload = {
        "timestamp": _ts(base, offset),
        "level": "INFO",
        "service": extra.pop("service", "gateway"),
        "actor_id": actor_id,
        "source_ip": source_ip,
        "action": action,
        "result": result,
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "message": action,
    }
    payload.update(extra)
    return payload


def build_events(base: datetime | None = None) -> list[dict]:
    base = base or datetime.now(timezone.utc)
    events: list[dict] = []

    # --- Benign baseline ---
    events.append(
        _event(
            base=base,
            offset=0,
            action="login",
            result="ok",
            actor_id="usr-member-a",
            source_ip="10.0.0.21",
            service="identity",
        )
    )
    events.append(
        _event(
            base=base,
            offset=2,
            action="submit_order",
            result="ok",
            actor_id="usr-member-a",
            source_ip="10.0.0.21",
            service="gateway",
        )
    )
    events.append(
        _event(
            base=base,
            offset=5,
            action="login",
            result="ok",
            actor_id="usr-admin",
            source_ip="10.0.0.5",
            service="identity",
            actor_role="administrator",
        )
    )
    events.append(
        _event(
            base=base,
            offset=8,
            action="change_role",
            result="ok",
            actor_id="usr-admin",
            source_ip="10.0.0.5",
            service="identity",
            actor_role="administrator",
            detail={"previous_role": "operations", "new_role": "operations"},
        )
    )

    # --- Malicious: brute force ---
    for i in range(6):
        events.append(
            _event(
                base=base,
                offset=20 + i,
                action="login",
                result="denied",
                actor_id="usr-member-a",
                source_ip="203.0.113.50",
                service="identity",
                correlation_id=f"bf-corr-{i}",
            )
        )

    # --- Malicious: privilege escalation (member forges success / bypass) ---
    events.append(
        _event(
            base=base,
            offset=40,
            action="change_role",
            result="ok",
            actor_id="usr-member-b",
            source_ip="10.0.0.22",
            service="identity",
            actor_role="member",
            detail={"previous_role": "member", "new_role": "administrator"},
            correlation_id="priv-esc-1",
        )
    )
    events.append(
        _event(
            base=base,
            offset=41,
            action="change_role",
            result="denied",
            actor_id="usr-analyst",
            source_ip="10.0.0.30",
            service="identity",
            actor_role="security_analyst",
            detail={"requested_role": "administrator"},
            correlation_id="priv-esc-denied",
        )
    )

    # --- Malicious: cross-tenant access ---
    events.append(
        _event(
            base=base,
            offset=50,
            action="get_order",
            result="denied_cross_tenant",
            actor_id="usr-member-b",
            source_ip="10.0.0.22",
            service="matching-engine",
            correlation_id="xt-1",
        )
    )
    events.append(
        _event(
            base=base,
            offset=51,
            action="get_order",
            result="denied_cross_tenant",
            actor_id="usr-member-b",
            source_ip="10.0.0.22",
            service="matching-engine",
            correlation_id="xt-2",
        )
    )

    # --- Malicious: suspicious source IP (denylist) ---
    events.append(
        _event(
            base=base,
            offset=60,
            action="login",
            result="ok",
            actor_id="usr-member-a",
            source_ip="198.51.100.66",
            service="identity",
            correlation_id="bad-ip-1",
        )
    )
    events.append(
        _event(
            base=base,
            offset=61,
            action="submit_order",
            result="ok",
            actor_id="usr-member-a",
            source_ip="198.51.100.66",
            service="gateway",
            correlation_id="bad-ip-2",
        )
    )

    # --- Malicious: order-rate anomaly ---
    for i in range(10):
        events.append(
            _event(
                base=base,
                offset=70 + i * 0.5,
                action="submit_order",
                result="ok" if i < 5 else "rate_limited",
                actor_id="usr-member-a",
                source_ip="10.0.0.21",
                service="gateway",
                correlation_id=f"rate-{i}",
            )
        )

    events.sort(key=lambda e: e["timestamp"])
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "logs" / "synthetic-events.jsonl",
        help="Output JSONL path",
    )
    parser.add_argument(
        "--scenario",
        choices=["all", "benign", "brute-force", "privilege-escalation", "cross-tenant-access", "suspicious-source-ip", "market-data-anomaly"],
        default="all",
    )
    args = parser.parse_args(argv)

    events = build_events()
    if args.scenario != "all" and args.scenario != "benign":
        # Filter loosely by correlation / action patterns for single-rule demos
        rule_filters = {
            "brute-force": lambda e: e.get("result") == "denied" and e.get("action") == "login",
            "privilege-escalation": lambda e: e.get("action") == "change_role",
            "cross-tenant-access": lambda e: e.get("result") == "denied_cross_tenant",
            "suspicious-source-ip": lambda e: e.get("source_ip") in {"198.51.100.66", "203.0.113.99"},
            "market-data-anomaly": lambda e: str(e.get("correlation_id", "")).startswith("rate-"),
        }
        # Keep a little benign context + scenario events
        benign = [e for e in events if e.get("source_ip", "").startswith("10.0.0.") and e.get("result") == "ok"][:2]
        focused = [e for e in events if rule_filters[args.scenario](e)]
        events = benign + focused
    elif args.scenario == "benign":
        events = [e for e in events if e.get("result") == "ok" and e.get("source_ip", "").startswith("10.")]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")
    print(f"Wrote {len(events)} events to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
