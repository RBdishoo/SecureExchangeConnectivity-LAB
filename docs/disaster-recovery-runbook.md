# Disaster Recovery Runbook (stub)

> Week 1 stub. Backup/restore scripts and integrity checks arrive in Week 4.

## Purpose

Recover the lab PostgreSQL dataset into a DR-style environment and verify integrity.

## Placeholder steps

1. Take a logical backup (`scripts/backup.sh` — forthcoming).
2. Restore into a clean Postgres instance on an isolated network.
3. Run `scripts/verify-backup.py` integrity checks.
4. Record RPO/RTO observations for the portfolio write-up.

## Related diagram

[`diagrams/recovery-flow.mmd`](../diagrams/recovery-flow.mmd)
