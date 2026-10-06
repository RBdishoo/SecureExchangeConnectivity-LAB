#!/usr/bin/env python3
"""CLI wrapper: generate (optional) + run detections."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from detections.engine import main as engine_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", type=Path, default=ROOT / "data" / "logs" / "synthetic-events.jsonl")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "alerts")
    parser.add_argument("--generate", action="store_true", help="Run generate-events.py first")
    parser.add_argument("--rule-id", action="append", default=None)
    args = parser.parse_args(argv)

    if args.generate:
        gen = ROOT / "scripts" / "generate-events.py"
        subprocess.check_call([sys.executable, str(gen), "--out", str(args.logs)])

    cli = ["--logs", str(args.logs), "--out", str(args.out)]
    if args.rule_id:
        for rid in args.rule_id:
            cli.extend(["--rule-id", rid])
    return engine_main(cli)


if __name__ == "__main__":
    raise SystemExit(main())
