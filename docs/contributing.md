# Contributing

## Getting started

1. Fork and clone the repository.
2. Follow **[deployment.md](deployment.md)** to run the stack locally.
3. Branch from `main`:

   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
make up
make test
```

## Guidelines

- Python **3.11+**
- Type hints on public functions; docstrings for modules and public APIs
- **`structlog`** for logging (not `print()`)
- Validate at boundaries with **Pydantic** schemas

## Tests and verification

- Add tests under `tests/`
- Before a PR: `make test` and, with Docker up, `make verify`

## Pull requests

- Rebase or merge `main` as needed
- Describe **what** changed and **why**
- One focused change per PR where possible

## Issues

- Include repro steps, expected vs actual behaviour
- Mention OS, Docker, and Python versions

## Architecture decisions

Significant design choices should be recorded as an ADR in **`docs/decisions/`** (see existing ADRs for tone and structure).

## License

By contributing, you agree your contributions are licensed under the same terms as the project (**MIT**, if that is the repo license).
