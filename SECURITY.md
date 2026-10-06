# Security Policy

## Educational project notice

This repository is a **synthetic educational lab**. It does not process real market data,
customer credentials, or production exchange traffic. Do not connect it to live trading
systems or store real secrets in the codebase.

## Reporting a vulnerability

If you discover a security issue in this educational codebase (for example, unsafe
defaults that would be dangerous if someone mistakenly reused the patterns):

1. Open a GitHub issue labeled `security` with a clear description, or
2. Contact the repository maintainers privately if the finding could be harmful if
   disclosed publicly.

Please include steps to reproduce and an assessment of impact in a lab context.

## Secret handling

- Never commit `.env` files, API keys, passwords, or tokens.
- Use placeholder values only (for example `changeme-lab-only`).
- Gitleaks is configured via `.gitleaks.toml`; run it before pushing.
- Structured logs must not include bearer tokens or raw passwords.

## Supported versions

Only the `main` branch and the latest released lab snapshot are considered supported
for educational updates.
