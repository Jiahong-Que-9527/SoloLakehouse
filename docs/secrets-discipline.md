# Secrets Discipline (v2.9 Block D)

v2.9 introduces a local secrets split without changing the protected v2.5
Compose service set or adding a managed secret provider (that is v3.0 / ADR-009).

## Split env files

| File | Purpose |
|---|---|
| `.env.shared.example` | Non-secret runtime configuration template |
| `.env.secrets.example` | Credential/token template |
| `.env.shared` / `.env.secrets` | Local copies (gitignored) |
| `.env` | Generated merge for Compose compatibility |

```bash
make init-env
make secrets-discipline
```

## Rotation drill

Record a manual rotation rehearsal:

```bash
make secrets-rotation-drill ROTATED_KEYS=POSTGRES_PASSWORD,S3_SECRET_KEY
```

Then verify the platform:

```bash
make verify
```

## Limitations

Reference evidence only. Managed secrets, automatic rotation, and production
least-privilege enforcement belong to v3.0.
