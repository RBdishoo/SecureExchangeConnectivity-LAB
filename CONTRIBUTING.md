# Contributing

Thank you for interest in the Secure Exchange Connectivity Lab.

## Scope

This is an educational reference lab. Contributions should reinforce secure design
concepts (segmentation, least privilege, structured logging, recovery) using
**synthetic** data only.

## Ground rules

1. Keep the educational disclaimer intact in `README.md`.
2. Do not add real market data, customer PII, live credentials, or connections to
   real exchange infrastructure.
3. Prefer small, focused pull requests with a clear security or educational rationale.
4. Do not commit secrets. Run Gitleaks locally when available.
5. Match existing Python/FastAPI and Docker Compose patterns.

## Development workflow

```bash
git checkout -b feature/your-change
docker compose up --build
# make your changes, add tests when behavior changes
git commit -m "Describe the change"
```

## Code style

- Python 3.12+, FastAPI, structured JSON logging.
- Prefer clear names over clever abstractions.
- Document trust-boundary and security implications in PR descriptions.

## Pull requests

Include:

- What changed and why
- How you verified it (`docker compose up`, health checks, log samples)
- Any known limitations
