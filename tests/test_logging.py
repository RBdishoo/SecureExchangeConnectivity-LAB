"""Week 1 smoke: structured logging helper produces required fields."""

from __future__ import annotations

import json
import logging
from io import StringIO

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))

from common.logging_utils import JsonFormatter, configure_logging, log_event  # noqa: E402


def test_json_log_contains_required_fields():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test-logging")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    log_event(
        logger,
        action="unit_test_action",
        result="ok",
        actor_id="member-lab-001",
        source_ip="203.0.113.10",
        correlation_id="corr-test-1",
    )

    line = stream.getvalue().strip()
    payload = json.loads(line)
    for key in ("timestamp", "actor_id", "source_ip", "action", "result", "correlation_id"):
        assert key in payload
    assert payload["action"] == "unit_test_action"
    assert payload["result"] == "ok"
    assert payload["actor_id"] == "member-lab-001"
    assert payload["source_ip"] == "203.0.113.10"
    assert payload["correlation_id"] == "corr-test-1"
