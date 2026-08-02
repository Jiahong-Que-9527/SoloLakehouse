# Promotion Discipline (v2.9 Block B)

SoloLakehouse records promotion and rollback evidence on the protected v2.5
runtime without adding new platform services.

## Promotion chain

```text
dev -> staging -> production
```

| Variable | Purpose |
|---|---|
| `PROMOTION_STAGE` | Current stage (`dev`, `staging`, `production`) |
| `ENVIRONMENT` | Fallback mapper (`local` -> `dev`) |
| `ROLLBACK_TARGET_TAG` | Known-good git tag for rollback drills and promotion evidence |
| `GIT_COMMIT` | Commit stamped into promotion evidence |

## Commands

```bash
# Requires stack health + ROLLBACK_TARGET_TAG
make promotion-evidence

# Explicit target stage
make promotion-evidence TARGET_STAGE=staging

# Rollback readiness drill (fails if runtime checks fail)
make rollback-drill

# Record drill output without claiming readiness
make rollback-drill ALLOW_UNHEALTHY=1
```

## Gates evaluated

Promotion evidence runs:

1. All `make verify` service checks
2. Governed dataset contract validation
3. Rollback tag resolution (`git rev-parse ROLLBACK_TARGET_TAG`)
4. Required runtime environment variables

If any gate fails, **no promotion manifest is emitted**.

## Limitations

Reference evidence only — not a compliance certification. Full multi-environment
automation belongs to v3.0 (ADR-008).
