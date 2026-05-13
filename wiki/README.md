# wiki/ — staging directory for GitHub Wiki content

These files are **not** rendered by GitHub from this folder. To publish them, push to the wiki's own git repo.

## Publish workflow

```bash
# One-time: clone the wiki repo as a sibling
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.wiki.git ../SoloLakehouse.wiki

# Copy / sync content
cp wiki/*.md ../SoloLakehouse.wiki/

# Commit & push
cd ../SoloLakehouse.wiki
git add .
git commit -m "Update wiki"
git push
```

> The GitHub Wiki must be enabled in repo Settings → Features → Wikis, and you must have created at least one page in the web UI before the `.wiki.git` repo exists.

## Naming conventions

- Filename (with hyphens) becomes the URL slug **and** the displayed title (hyphens shown as spaces).
- `Home.md` is the landing page.
- `_Sidebar.md` and `_Footer.md` are special — they appear on every page.

## Pages in this skeleton

| File | Purpose |
|---|---|
| `Home.md` | Landing page with audience routing |
| `_Sidebar.md` / `_Footer.md` | Site-wide nav and footer |
| `30-Second-Pitch.md` | For reviewers / hiring managers |
| `Architecture-at-a-Glance.md` | For reviewers — visual + summary |
| `Compliance-Story.md` | DORA / BaFin / AI Act elevator |
| `Quick-Start.md` | TL;DR run instructions |
| `FAQ.md` | Recurring questions |
| `Troubleshooting.md` | Common local-stack problems |
| `Glossary.md` | Plain-language term list |
| `Reading-Order.md` | Onboarding tour for contributors |
| `Design-Decisions-Tour.md` | ADR narrative tour |
| `How-to-Add-a-New-Source.md` | End-to-end walkthrough |
| `Where-We-Are.md` | v2.5 snapshot |
| `Why-v3-is-Governance-First.md` | v3 rationale |
