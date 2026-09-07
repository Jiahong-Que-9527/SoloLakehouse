# Remote UI access with Tailscale Serve

FinLakehouse binds all operator UIs to `127.0.0.1` in Docker Compose so they are
not reachable from the public internet. **Tailscale Serve** exposes those local
ports to your **tailnet only**, with HTTPS terminated by Tailscale — no SSH port
forwarding required.

## One-time setup

### 1. Install Tailscale on your laptop

Join the same tailnet as the FinLakehouse host (`fin`).

### 2. Enable Serve on the FinLakehouse node

On the server, run:

```bash
make serve-ui-up
```

If Serve is not yet enabled for your tailnet, the command prints an admin URL
like:

```text
https://login.tailscale.com/f/serve?node=...
```

Open that link while signed in as a **tailnet admin**, approve Serve for this
node, then run `make serve-ui-up` again.

### 3. (Recommended) Restrict access with ACLs

In the [Tailscale ACL policy](https://login.tailscale.com/admin/acls), limit who
can reach `fin` on the Serve ports (443, 5000, 8080, 8088, 8585, 9001). Example
pattern:

```json
"grants": [
  {
    "src": ["autogroup:member"],
    "dst": ["tag:finlakehouse"],
    "ports": ["443", "5000", "8080", "8088", "8585", "9001"]
  }
]
```

Tag the `fin` node as `tag:finlakehouse` in the admin console if you use tags.

## Daily use

After `make serve-ui-up` (or once after reboot — Serve with `--bg` persists
across Tailscale restarts):

```bash
make serve-ui-urls
```

Example output (your hostname will differ):

| UI | URL |
|----|-----|
| Dagster | `https://fin.tail0f631b.ts.net/` |
| Trino | `https://fin.tail0f631b.ts.net:8080/` |
| Superset | `https://fin.tail0f631b.ts.net:8088/` |
| OpenMetadata | `https://fin.tail0f631b.ts.net:8585/` |
| MLflow | `https://fin.tail0f631b.ts.net:5000/` |
| MinIO Console | `https://fin.tail0f631b.ts.net:9001/` |

Open these URLs from any device on the tailnet (MacBook, phone with Tailscale,
etc.).

## Operations

```bash
make serve-ui-up       # register proxies (idempotent)
make serve-ui-status   # show tailscale serve status + URLs
make serve-ui-down     # tailscale serve reset
```

Serve proxies target **loopback** ports from Compose; keep the stack running
(`make verify`).

## Security notes

- **Not public internet** — only tailnet members (per ACL) can connect. Do not use
  `tailscale funnel` for these UIs.
- **Still demo-grade auth** — Superset and OpenMetadata have logins; Trino/Dagster
  are weaker. Treat tailnet membership as the primary gate.
- **SSH tunnels** remain valid if Serve is disabled; this doc supersedes manual
  `-L` mapping for day-to-day use.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Serve is not enabled on your tailnet` | Open the printed admin URL and enable Serve |
| 502 / connection refused | Run `make verify`; ensure the target container is up |
| Works on laptop but not phone | Confirm phone has Tailscale connected; check ACLs |
| Serve lost after `tailscale down` | Run `make serve-ui-up` again |
