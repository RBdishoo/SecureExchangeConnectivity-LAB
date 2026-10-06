"""Sigma-style YAML detection engine for synthetic lab JSON logs."""

from __future__ import annotations

import ipaddress
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _event_matches_selection(event: dict[str, Any], selection: dict[str, Any]) -> bool:
    if "action" in selection and event.get("action") != selection["action"]:
        return False
    if "result" in selection and event.get("result") != selection["result"]:
        return False
    if "action_any" in selection:
        action = str(event.get("action", ""))
        if not any(action == a or action.endswith(a) or a in action for a in selection["action_any"]):
            return False
    if "result_any" in selection:
        result = str(event.get("result", ""))
        if result not in selection["result_any"] and not any(r in result for r in selection["result_any"]):
            return False
    return True


def _ip_in_cidrs(ip: str, cidrs: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    for cidr in cidrs:
        try:
            if addr in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


@dataclass
class Alert:
    alert_id: str
    rule_id: str
    title: str
    level: str
    description: str
    triggered_at: str
    actor_id: str | None
    source_ip: str | None
    correlation_ids: list[str] = field(default_factory=list)
    event_count: int = 0
    evidence: list[dict[str, Any]] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "title": self.title,
            "level": self.level,
            "description": self.description,
            "triggered_at": self.triggered_at,
            "actor_id": self.actor_id,
            "source_ip": self.source_ip,
            "correlation_ids": self.correlation_ids,
            "event_count": self.event_count,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
        }


DEFAULT_RECOMMENDATIONS = {
    "brute-force": "Contain: lock or reset the targeted account; block source IP at edge; review subsequent successful logins.",
    "privilege-escalation": "Contain: revert unauthorized role; invalidate sessions; review admin audit chain and gateway JWT secret integrity.",
    "cross-tenant-access": "Contain: confirm denial held; notify member firm; watch for repeated probes from same actor/IP.",
    "suspicious-source-ip": "Contain: challenge or block the source IP; require step-up auth for the actor; verify allowlist currency.",
    "market-data-anomaly": "Contain: throttle or suspend the member session; inspect client automation; verify rate-limit config.",
}


class DetectionEngine:
    def __init__(self, rules_dir: Path | None = None):
        self.rules_dir = rules_dir or (ROOT / "detections")
        self.rules = self.load_rules()

    def load_rules(self) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        for path in sorted(self.rules_dir.glob("*.yml")):
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if not data.get("id"):
                continue
            data["_path"] = str(path)
            rules.append(data)
        return rules

    def load_events(self, log_path: Path) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        text = log_path.read_text(encoding="utf-8").strip()
        if not text:
            return events
        # Support JSONL and a JSON list.
        if text.startswith("["):
            payload = json.loads(text)
            if isinstance(payload, list):
                return [e for e in payload if isinstance(e, dict)]
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

    def run(self, events: list[dict[str, Any]], rule_ids: list[str] | None = None) -> list[Alert]:
        alerts: list[Alert] = []
        for rule in self.rules:
            if rule_ids and rule["id"] not in rule_ids:
                continue
            alerts.extend(self._evaluate_rule(rule, events))
        return alerts

    def run_on_file(self, log_path: Path, rule_ids: list[str] | None = None) -> list[Alert]:
        return self.run(self.load_events(log_path), rule_ids=rule_ids)

    def write_alerts(self, alerts: list[Alert], out_dir: Path) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for alert in alerts:
            path = out_dir / f"{alert.alert_id}.json"
            path.write_text(json.dumps(alert.to_dict(), indent=2), encoding="utf-8")
            paths.append(path)
        index = out_dir / "alerts.json"
        index.write_text(
            json.dumps([a.to_dict() for a in alerts], indent=2),
            encoding="utf-8",
        )
        return paths

    def _evaluate_rule(self, rule: dict[str, Any], events: list[dict[str, Any]]) -> list[Alert]:
        selection = rule.get("detection", {}).get("selection", {})
        condition = rule.get("detection", {}).get("condition", {})
        timeframe = int(rule.get("detection", {}).get("timeframe_seconds", 300))
        matched = [e for e in events if _event_matches_selection(e, selection)]
        ctype = condition.get("type")

        if ctype == "threshold":
            return self._threshold_alerts(rule, matched, condition, timeframe)
        if ctype == "match_any":
            return self._match_any_alerts(rule, matched, condition)
        if ctype == "suspicious_ip":
            return self._suspicious_ip_alerts(rule, matched, condition)
        if ctype == "privilege_escalation":
            return self._privilege_alerts(rule, matched, condition)
        return []

    def _base_alert(
        self,
        rule: dict[str, Any],
        evidence: list[dict[str, Any]],
        actor_id: str | None = None,
        source_ip: str | None = None,
    ) -> Alert:
        corr = sorted(
            {
                str(e.get("correlation_id"))
                for e in evidence
                if e.get("correlation_id")
            }
        )
        if actor_id is None and evidence:
            actor_id = evidence[0].get("actor_id")
        if source_ip is None and evidence:
            source_ip = evidence[0].get("source_ip")
        return Alert(
            alert_id=str(uuid.uuid4()),
            rule_id=rule["id"],
            title=rule.get("title", rule["id"]),
            level=rule.get("level", "medium"),
            description=str(rule.get("description", "")).strip(),
            triggered_at=datetime.now(timezone.utc).isoformat(),
            actor_id=actor_id,
            source_ip=source_ip,
            correlation_ids=corr,
            event_count=len(evidence),
            evidence=evidence[:20],
            recommendation=DEFAULT_RECOMMENDATIONS.get(
                rule["id"], "Contain: investigate actor, source IP, and correlated events."
            ),
        )

    def _threshold_alerts(
        self,
        rule: dict[str, Any],
        matched: list[dict[str, Any]],
        condition: dict[str, Any],
        timeframe: int,
    ) -> list[Alert]:
        group_by = condition.get("group_by", "actor_id")
        count = int(condition.get("count", 5))
        buckets: dict[str, list[dict[str, Any]]] = {}
        for event in matched:
            key = str(event.get(group_by) or "unknown")
            buckets.setdefault(key, []).append(event)

        alerts: list[Alert] = []
        window = timedelta(seconds=timeframe)
        for key, items in buckets.items():
            timed = [( _parse_ts(e.get("timestamp")) or datetime.now(timezone.utc), e) for e in items]
            timed.sort(key=lambda x: x[0])
            left = 0
            for right in range(len(timed)):
                while timed[right][0] - timed[left][0] > window:
                    left += 1
                if right - left + 1 >= count:
                    evidence = [e for _, e in timed[left : right + 1]]
                    alerts.append(
                        self._base_alert(
                            rule,
                            evidence,
                            actor_id=key if group_by == "actor_id" else evidence[0].get("actor_id"),
                            source_ip=evidence[0].get("source_ip"),
                        )
                    )
                    break
        return alerts

    def _match_any_alerts(
        self,
        rule: dict[str, Any],
        matched: list[dict[str, Any]],
        condition: dict[str, Any],
    ) -> list[Alert]:
        min_count = int(condition.get("min_count", 1))
        if len(matched) < min_count:
            return []
        # One alert per actor for clarity
        by_actor: dict[str, list[dict[str, Any]]] = {}
        for event in matched:
            by_actor.setdefault(str(event.get("actor_id") or "unknown"), []).append(event)
        return [self._base_alert(rule, evs, actor_id=actor) for actor, evs in by_actor.items()]

    def _suspicious_ip_alerts(
        self,
        rule: dict[str, Any],
        matched: list[dict[str, Any]],
        condition: dict[str, Any],
    ) -> list[Alert]:
        allow = condition.get("allowlist_cidrs", [])
        deny = set(condition.get("denylist_ips", []))
        hits: list[dict[str, Any]] = []
        for event in matched:
            ip = str(event.get("source_ip") or "")
            if not ip or ip == "unknown":
                continue
            if ip in deny or not _ip_in_cidrs(ip, allow):
                hits.append(event)
        if not hits:
            return []
        by_ip: dict[str, list[dict[str, Any]]] = {}
        for event in hits:
            by_ip.setdefault(str(event.get("source_ip")), []).append(event)
        return [
            self._base_alert(rule, evs, source_ip=ip, actor_id=evs[0].get("actor_id"))
            for ip, evs in by_ip.items()
        ]

    def _privilege_alerts(
        self,
        rule: dict[str, Any],
        matched: list[dict[str, Any]],
        condition: dict[str, Any],
    ) -> list[Alert]:
        elevate_to = set(condition.get("elevate_to", ["administrator"]))
        forbid = set(condition.get("forbid_actor_roles_on_success", []))
        hits: list[dict[str, Any]] = []
        for event in matched:
            detail = event.get("detail") or {}
            if isinstance(detail, str):
                try:
                    detail = json.loads(detail)
                except json.JSONDecodeError:
                    detail = {}
            new_role = detail.get("new_role") or detail.get("requested_role")
            actor_role = event.get("actor_role") or detail.get("actor_role")
            result = event.get("result")
            if result == "ok" and new_role in elevate_to:
                hits.append(event)
            elif result == "ok" and actor_role in forbid:
                hits.append(event)
            elif result == "denied" and new_role in elevate_to:
                # suspicious attempt to become admin
                hits.append(event)
        if not hits:
            return []
        by_actor: dict[str, list[dict[str, Any]]] = {}
        for event in hits:
            by_actor.setdefault(str(event.get("actor_id") or "unknown"), []).append(event)
        return [self._base_alert(rule, evs, actor_id=actor) for actor, evs in by_actor.items()]


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run lab detection rules against JSON/JSONL logs")
    parser.add_argument("--logs", type=Path, required=True, help="Path to JSONL/JSON log file")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "alerts")
    parser.add_argument("--rules", type=Path, default=None)
    parser.add_argument("--rule-id", action="append", default=None)
    args = parser.parse_args(argv)

    engine = DetectionEngine(rules_dir=args.rules)
    alerts = engine.run_on_file(args.logs, rule_ids=args.rule_id)
    paths = engine.write_alerts(alerts, args.out)
    print(json.dumps({"alert_count": len(alerts), "written": [str(p) for p in paths]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
