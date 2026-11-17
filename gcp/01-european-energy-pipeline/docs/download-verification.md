# Bounded download verification

Live check on 2026-11-17, for German actual total load only. This checks one
small historical window, not continuous uptime, full-year coverage or all
metrics. Downloaded data and runtime outputs remain outside Git.

## Provider review

Reviewed the [data-use notice](https://www.smard.de/home/datennutzung),
[website terms](https://www.smard.de/home/impressum) and
[download centre](https://www.smard.de/home/downloadcenter/download-marktdaten).
The terms require access that does not impair other visitors. The selected
load data is offered under CC BY 4.0; the wholesale-price review remains
separate. No numeric API allowance or versioned compatibility promise was
identified. See [data use](data-use.md) for implementation boundaries.

Confirmed the endpoint and JSON body against the provider's own
[download-centre script](https://www.smard.de/resource/themes/bnetza/js/apps/download-center-209416-11.js).
Its `downloadMarketData` call uses POST to
`/nip-download-manager/nip/download/market-data`, a `request_form` array,
module IDs, region, resolution, format, millisecond timestamps, `discrete`
type and language. The site's inclusive selected end day is converted to
the following local midnight; the CLI takes that exclusive midnight directly.
The script URL is observed evidence, not a stable API specification.

## Live result

```bash
energy-pipeline download --from 2026-06-08 --until 2026-06-09 \
  --cache downloads --normalize-output output/live-smoke
```

- `robots.txt` returned HTTP 404; the client treated this as no supplied robots
  policy, while retaining the website-term restrictions.
- The client made one policy GET and one CSV POST, paced at least five seconds
  apart. No load-data retries or alternate-endpoint calls were needed.
- Local window: `[2026-06-08, 2026-06-09)`, Europe/Berlin.
- UTC window: `[2026-06-07T22:00:00Z, 2026-06-08T22:00:00Z)`.
- Retrieved at: `2026-11-17T13:04:00.052036+00:00`.
- Normalization passed with 96 rows.
- Raw SHA-256: `d047e5b2a84a3a9261ea4caa84e07ebc38c987b0cb8ad41fbd0efb26ef85e6f8`.
- Repeated the command using the cache, successfully within the network-restricted
  environment. No source requests were needed, and retrieval time was preserved.
- Both normalized outputs had SHA-256
  `b87dec2698de2d84341ddeb4fcf0099b513139f92656638104bfc60c1d59dcb5`.

## Offline checks and next evidence

Automated tests use fake HTTP responses and a fake clock for access denial,
robots restrictions, cooldown persistence, retry limits, request pacing,
cache integrity, file locking and download-to-normalization provenance.
No CI test polls the provider or triggers a live export.

Next evidence: a bounded coverage audit including both clock changes, followed
by a separately planned yearly audit and availability measurements. Scheduling,
distributed concurrency and revision-refresh behaviour are not verified by
this one-day check.
