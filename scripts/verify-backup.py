#!/usr/bin/env python3
"""Verify a lab Postgres backup artifact and optional DR restore integrity."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_checksum_file(path: Path) -> str | None:
    if not path.exists():
        return None
    line = path.read_text(encoding="utf-8").strip().splitlines()[0]
    return line.split()[0]


def analyze_dump(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "bytes": path.stat().st_size,
        "non_empty": path.stat().st_size > 0,
        "has_orders_ddl": bool(
            re.search(r"CREATE TABLE(?: IF NOT EXISTS)?\s+public\.orders\b", text, re.I)
            or re.search(r"CREATE TABLE(?: IF NOT EXISTS)?\s+orders\b", text, re.I)
        ),
        "copy_or_insert_orders": bool(
            re.search(r"COPY\s+(?:public\.)?orders\b", text, re.I)
            or re.search(r"INSERT INTO\s+(?:public\.)?orders\b", text, re.I)
        ),
        "insert_statements": len(re.findall(r"^INSERT INTO", text, flags=re.M)),
    }


def compose_cmd() -> list[str]:
    # Prefer sudo docker compose when required.
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            check=True,
            capture_output=True,
        )
        # Probe permission
        probe = subprocess.run(
            ["docker", "compose", "ps"],
            capture_output=True,
        )
        if probe.returncode == 0:
            return ["docker", "compose"]
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return ["sudo", "docker", "compose"]


def dr_order_count(service: str = "postgres-dr", user: str = "labuser", db: str = "seclab") -> int | None:
    cmd = compose_cmd() + [
        "exec",
        "-T",
        service,
        "psql",
        "-U",
        user,
        "-d",
        db,
        "-Atc",
        "SELECT COUNT(*) FROM orders;",
    ]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return int(proc.stdout.strip() or "0")
    except (subprocess.CalledProcessError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backup",
        type=Path,
        default=None,
        help="Path to .sql dump (defaults to newest under data/backups)",
    )
    parser.add_argument(
        "--check-dr",
        action="store_true",
        help="Also query postgres-dr for orders row count",
    )
    parser.add_argument(
        "--min-orders",
        type=int,
        default=0,
        help="Minimum expected orders rows in DR (when --check-dr)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON report path",
    )
    args = parser.parse_args(argv)

    backup = args.backup
    if backup is None:
        backups = sorted((ROOT / "data" / "backups").glob("seclab-*.sql"))
        if not backups:
            print("ERROR: no backup file found; run scripts/backup.sh first", file=sys.stderr)
            return 1
        backup = backups[-1]

    if not backup.exists():
        print(f"ERROR: backup not found: {backup}", file=sys.stderr)
        return 1

    digest = sha256_file(backup)
    expected = parse_checksum_file(Path(str(backup) + ".sha256"))
    analysis = analyze_dump(backup)
    report = {
        "backup_file": str(backup),
        "sha256": digest,
        "sha256_match": (expected is None) or (expected == digest),
        "expected_sha256": expected,
        **analysis,
        "dr_orders_count": None,
        "ok": False,
    }

    ok = (
        report["non_empty"]
        and report["sha256_match"]
        and report["has_orders_ddl"]
    )
    if args.check_dr:
        count = dr_order_count()
        report["dr_orders_count"] = count
        ok = ok and count is not None and count >= args.min_orders

    report["ok"] = ok
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
