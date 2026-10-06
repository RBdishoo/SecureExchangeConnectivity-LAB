"""Alerting / security monitoring — detection API + health."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE, _HERE.parent, _HERE.parents[1] if len(_HERE.parents) > 1 else _HERE):
    marker = _candidate / "common"
    dets = _candidate / "detections"
    if marker.is_dir() or dets.is_dir():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))

# Local monorepo: services/alerting -> repo root
_REPO_CANDIDATE = _HERE.parents[1] if _HERE.name != "app" else _HERE
if (_REPO_CANDIDATE / "detections").is_dir() and str(_REPO_CANDIDATE) not in sys.path:
    sys.path.insert(0, str(_REPO_CANDIDATE))

from common.logging_utils import configure_logging, log_event  # noqa: E402
from common.middleware import StructuredLoggingMiddleware  # noqa: E402
from detections.engine import DetectionEngine  # noqa: E402

SERVICE_NAME = "alerting"
logger = configure_logging(SERVICE_NAME)

ALERTS_DIR = Path(os.getenv("ALERTS_DIR", str(_REPO_CANDIDATE / "data" / "alerts")))
LOGS_PATH = Path(os.getenv("LOGS_PATH", str(_REPO_CANDIDATE / "data" / "logs" / "synthetic-events.jsonl")))
RULES_DIR = Path(os.getenv("RULES_DIR", str(_REPO_CANDIDATE / "detections")))

app = FastAPI(
    title="Secure Exchange Connectivity Lab — Alerting",
    description="Educational detection/alerting service. Synthetic events only.",
    version="0.3.0",
)
app.add_middleware(StructuredLoggingMiddleware, logger=logger)


class RunRequest(BaseModel):
    logs_path: str | None = None
    rule_ids: list[str] | None = None


@app.get("/health")
def health() -> dict:
    log_event(logger, action="health_check", result="ok", actor_id="system")
    return {"status": "ok", "service": SERVICE_NAME, "zone": "security"}


@app.get("/")
def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "role": "alerting",
        "trust_boundary": "Lives on security-net; detection pipeline for Week 3",
        "endpoints": [
            "GET /health",
            "GET /detections",
            "POST /detections/run",
            "GET /alerts",
            "GET /alerts/{alert_id}",
        ],
    }


@app.get("/detections")
def list_detections() -> dict:
    engine = DetectionEngine(rules_dir=RULES_DIR)
    return {
        "rules": [
            {
                "id": r.get("id"),
                "title": r.get("title"),
                "level": r.get("level"),
                "status": r.get("status"),
            }
            for r in engine.rules
        ]
    }


@app.post("/detections/run")
def run_detections(body: RunRequest | None = None) -> dict:
    body = body or RunRequest()
    log_path = Path(body.logs_path) if body.logs_path else LOGS_PATH
    if not log_path.exists():
        raise HTTPException(status_code=404, detail=f"Log file not found: {log_path}")
    engine = DetectionEngine(rules_dir=RULES_DIR)
    alerts = engine.run_on_file(log_path, rule_ids=body.rule_ids)
    engine.write_alerts(alerts, ALERTS_DIR)
    log_event(logger, action="run_detections", result="ok", actor_id="system")
    return {"alert_count": len(alerts), "alerts": [a.to_dict() for a in alerts]}


@app.get("/alerts")
def list_alerts() -> dict:
    index = ALERTS_DIR / "alerts.json"
    if not index.exists():
        return {"alerts": []}
    return {"alerts": json.loads(index.read_text(encoding="utf-8"))}


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str) -> dict:
    path = ALERTS_DIR / f"{alert_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Alert not found")
    return json.loads(path.read_text(encoding="utf-8"))
