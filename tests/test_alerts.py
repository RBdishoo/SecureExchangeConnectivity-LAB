"""Tests that deliberately trigger each Week 3 detection rule."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from detections.engine import DetectionEngine  # noqa: E402


def _write_events(tmp_path: Path, events: list[dict]) -> Path:
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return path


def _build_corpus(tmp_path: Path) -> Path:
    gen_path = ROOT / "scripts" / "generate-events.py"
    spec = importlib.util.spec_from_file_location("generate_events", gen_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    events = mod.build_events()
    path = tmp_path / "synthetic-events.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def engine() -> DetectionEngine:
    return DetectionEngine(rules_dir=ROOT / "detections")


@pytest.fixture()
def corpus(tmp_path: Path) -> Path:
    return _build_corpus(tmp_path)


def test_all_five_rules_loaded(engine: DetectionEngine):
    ids = {r["id"] for r in engine.rules}
    assert ids >= {
        "brute-force",
        "privilege-escalation",
        "cross-tenant-access",
        "suspicious-source-ip",
        "market-data-anomaly",
    }


def test_brute_force_triggers(engine: DetectionEngine, corpus: Path):
    alerts = engine.run_on_file(corpus, rule_ids=["brute-force"])
    assert alerts, "brute-force should fire on synthetic denied logins"
    assert alerts[0].actor_id == "usr-member-a"
    assert alerts[0].event_count >= 5


def test_privilege_escalation_triggers(engine: DetectionEngine, corpus: Path):
    alerts = engine.run_on_file(corpus, rule_ids=["privilege-escalation"])
    assert alerts
    actors = {a.actor_id for a in alerts}
    assert "usr-member-b" in actors or "usr-analyst" in actors


def test_cross_tenant_triggers(engine: DetectionEngine, corpus: Path):
    alerts = engine.run_on_file(corpus, rule_ids=["cross-tenant-access"])
    assert alerts
    assert any(a.actor_id == "usr-member-b" for a in alerts)


def test_suspicious_source_ip_triggers(engine: DetectionEngine, corpus: Path):
    alerts = engine.run_on_file(corpus, rule_ids=["suspicious-source-ip"])
    assert alerts
    assert any(a.source_ip == "198.51.100.66" for a in alerts)


def test_order_rate_anomaly_triggers(engine: DetectionEngine, corpus: Path):
    alerts = engine.run_on_file(corpus, rule_ids=["market-data-anomaly"])
    assert alerts
    assert any(a.actor_id == "usr-member-a" for a in alerts)


def test_benign_baseline_does_not_fire_brute_force(engine: DetectionEngine, tmp_path: Path):
    events = [
        {
            "timestamp": "2026-10-06T12:00:00+00:00",
            "action": "login",
            "result": "ok",
            "actor_id": "usr-member-a",
            "source_ip": "10.0.0.21",
            "correlation_id": "b1",
        }
    ]
    path = _write_events(tmp_path, events)
    assert engine.run_on_file(path, rule_ids=["brute-force"]) == []


def test_write_alerts_roundtrip(engine: DetectionEngine, corpus: Path, tmp_path: Path):
    alerts = engine.run_on_file(corpus)
    assert len(alerts) >= 5
    out = tmp_path / "alerts"
    engine.write_alerts(alerts, out)
    index = json.loads((out / "alerts.json").read_text(encoding="utf-8"))
    assert len(index) == len(alerts)
    rule_ids = {a["rule_id"] for a in index}
    assert {
        "brute-force",
        "privilege-escalation",
        "cross-tenant-access",
        "suspicious-source-ip",
        "market-data-anomaly",
    } <= rule_ids
