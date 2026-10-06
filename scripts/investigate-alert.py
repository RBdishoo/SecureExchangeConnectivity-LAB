#!/usr/bin/env python3
"""Investigate a synthetic alert: timeline, actor, IP, correlation, containment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from detections.engine import DetectionEngine  # noqa: E402


def load_alert(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def related_events(logs: Path, alert: dict) -> list[dict]:
    engine = DetectionEngine()
    events = engine.load_events(logs)
    actor = alert.get("actor_id")
    ips = {alert.get("source_ip")} if alert.get("source_ip") else set()
    corrs = set(alert.get("correlation_ids") or [])
    related = []
    for event in events:
        if actor and event.get("actor_id") == actor:
            related.append(event)
            continue
        if event.get("source_ip") in ips:
            related.append(event)
            continue
        if event.get("correlation_id") in corrs:
            related.append(event)
            continue
    related.sort(key=lambda e: e.get("timestamp") or "")
    return related


def render_report(alert: dict, related: list[dict]) -> str:
    lines = [
        "# Alert investigation",
        "",
        f"- **Alert ID:** {alert.get('alert_id')}",
        f"- **Rule:** {alert.get('rule_id')} — {alert.get('title')}",
        f"- **Level:** {alert.get('level')}",
        f"- **Triggered at:** {alert.get('triggered_at')}",
        f"- **Actor / member ID:** {alert.get('actor_id')}",
        f"- **Source IP:** {alert.get('source_ip')}",
        f"- **Correlation IDs:** {', '.join(alert.get('correlation_ids') or []) or 'n/a'}",
        f"- **Evidence events:** {alert.get('event_count')}",
        "",
        "## Hypothesis",
        "",
        alert.get("description", "").strip() or "See detection catalog.",
        "",
        "## Timeline (related events)",
        "",
    ]
    for event in related[:50]:
        lines.append(
            f"- `{event.get('timestamp')}` | {event.get('service')} | "
            f"actor={event.get('actor_id')} ip={event.get('source_ip')} | "
            f"{event.get('action')} → {event.get('result')} | corr={event.get('correlation_id')}"
        )
    lines.extend(
        [
            "",
            "## Recommended containment",
            "",
            alert.get("recommendation")
            or "Contain: investigate actor, source IP, and correlated events; preserve logs.",
            "",
            "## Evidence sample",
            "",
            "```json",
            json.dumps((alert.get("evidence") or [])[:5], indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alert", type=Path, required=True, help="Path to alert JSON")
    parser.add_argument(
        "--logs",
        type=Path,
        default=ROOT / "data" / "logs" / "synthetic-events.jsonl",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional markdown output path",
    )
    args = parser.parse_args(argv)

    alert = load_alert(args.alert)
    related = related_events(args.logs, alert)
    report = render_report(alert, related)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"Wrote investigation to {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
