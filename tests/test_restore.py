"""Tests for backup verification helpers (dump integrity)."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_verify():
    path = ROOT / "scripts" / "verify-backup.py"
    spec = importlib.util.spec_from_file_location("verify_backup", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_analyze_dump_detects_orders_ddl(tmp_path: Path):
    mod = _load_verify()
    dump = tmp_path / "seclab-test.sql"
    dump.write_text(
        """
-- lab dump
CREATE TABLE public.orders (
    order_id text PRIMARY KEY,
    tenant_id text NOT NULL
);
INSERT INTO public.orders VALUES ('o1', 'TENANT_A');
""",
        encoding="utf-8",
    )
    analysis = mod.analyze_dump(dump)
    assert analysis["non_empty"] is True
    assert analysis["has_orders_ddl"] is True
    assert analysis["copy_or_insert_orders"] is True


def test_sha256_roundtrip(tmp_path: Path):
    mod = _load_verify()
    dump = tmp_path / "seclab-test.sql"
    content = b"CREATE TABLE orders (id text);\n"
    dump.write_bytes(content)
    digest = mod.sha256_file(dump)
    assert digest == hashlib.sha256(content).hexdigest()
    checksum = tmp_path / "seclab-test.sql.sha256"
    checksum.write_text(f"{digest}  seclab-test.sql\n", encoding="utf-8")
    assert mod.parse_checksum_file(checksum) == digest


def test_verify_backup_cli_ok(tmp_path: Path):
    mod = _load_verify()
    dump = tmp_path / "seclab-test.sql"
    dump.write_text(
        "CREATE TABLE orders (order_id text);\nINSERT INTO orders VALUES ('1');\n",
        encoding="utf-8",
    )
    digest = mod.sha256_file(dump)
    (tmp_path / "seclab-test.sql.sha256").write_text(f"{digest}  seclab-test.sql\n", encoding="utf-8")
    report_path = tmp_path / "report.json"
    rc = mod.main(["--backup", str(dump), "--out", str(report_path)])
    assert rc == 0
    assert report_path.exists()


def test_verify_backup_cli_fails_empty(tmp_path: Path):
    mod = _load_verify()
    dump = tmp_path / "empty.sql"
    dump.write_text("", encoding="utf-8")
    rc = mod.main(["--backup", str(dump)])
    assert rc == 2
