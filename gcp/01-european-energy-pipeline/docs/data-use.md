# Data use and compliance

Reviewed on 2026-11-17 against the provider's public terms. This note covers
German actual total load from SMARD (`moduleIds: [5000410]`, region `DE`).
The bounded local downloader is implemented; cloud publication remains planned.
This note records the basis and limits of that implementation, not provider
certification or a blanket legal guarantee. Recheck the terms when adding a
new metric, changing provider or preparing a public release.

## Data licence and permitted uses

SMARD's [data-use notice](https://www.smard.de/home/datennutzung) and
[download centre](https://www.smard.de/home/downloadcenter/download-marktdaten)
identify downloadable market data as CC BY 4.0. For the current load data,
this permits downloading, storing in Cloud Storage and BigQuery, processing,
public display and redistribution, including commercial use, subject to the
[licence conditions](https://creativecommons.org/licenses/by/4.0/).

When distributing source data or derived outputs:

- Credit the source as `Bundesnetzagentur | SMARD.de`.
- Link to the source and CC BY 4.0. Retain supplied licence, copyright and
  disclaimer notices where applicable.
- Identify changes, such as UTC conversion, unit conversion, filtering or
  aggregation. Do not imply that the provider endorses this project.
- Do not add legal or technical restrictions that prevent recipients from
  exercising the rights granted by the licence.

Keep the data licence separate from the repository's software licence. A
code licence does not replace the terms for bundled SMARD data. Website
text, images, logos and software are not automatically covered by the market
data licence; the [website terms](https://www.smard.de/home/impressum) treat
those separately.

## Attribution in project outputs

The fixture README already documents the source, licence, download date and
checksums. Preserve that information when copying fixtures elsewhere.

For future releases, place attribution, source and licence links, retrieval
time and a description of transformations in the accompanying release
metadata. Include an accessible notice in public charts, reports and API
documentation. G02 and G04 should carry these notices into their outputs.
These are project implementation choices for meeting the licence conditions,
not provider-mandated metadata field names.

Example for a normalized release; adjust the changes to match the actual work:

> Source: Bundesnetzagentur | SMARD.de — German actual total load.
> [Original data](https://www.smard.de/home/downloadcenter/download-marktdaten),
> licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
> Changes: timestamps converted to UTC; numeric formatting normalized.

## Automated downloads

The [website terms, item 5](https://www.smard.de/home/impressum) require access
that does not impair use by other visitors. The reviewed terms do not state
a numeric request limit or guarantee API compatibility or availability.
The data licence does not establish an unlimited request allowance.

The local downloader implements the following project operating practices:

- Use only the same CSV export endpoint as the official download page, with
  a descriptive project User-Agent. Do not impersonate browsers, follow
  redirects or fall back to other endpoints after refusal.
- Limit each request to the selected load metric and 1 to 31 past local days.
  Use one process per persistent cache and at least five seconds between
  request starts. Separate machines or caches are not coordinated; do not
  deploy parallel workers without additional coordination.
- Check robots policy before uncached downloads and retain it for 24 hours.
  Respect path restrictions and longer pacing directives. Treat 404 as absent
  robots policy; other policy errors stop acquisition. Robots permission is
  not a substitute for the website terms or data licence.
- Verify and reuse cached exports without a request. Preserve raw bytes,
  retrieval time, checksum, request parameters, attribution and licence links.
  The raw cache is immutable and does not currently refresh historical values.
- Stop immediately on 401/403 and persist the denial across invocations.
  On 429 or `Retry-After`, persist the cooldown and exit without an automatic
  retry. Honour both seconds and HTTP-date forms; missing/invalid guidance
  uses a one-hour cooldown. Do not delete state or change caches to bypass
  denial or cooldown; review persistent denial with the provider.
- Retry only 502/503/504 without retry guidance, at most twice with backoff.
  Do not automatically resend timed-out POSTs whose server-side outcome is
  unknown. Apply a timeout and response-size limit; reject changed CSV headers.

These limits are conservative project choices, not a numeric rate allowance,
API contract or approval published by SMARD. The website's export endpoint
may change. Reassess terms and provider guidance before changing the metric,
increasing volume or enabling unattended scheduling. An explicitly invoked
`prepare-year` command sequences 12 monthly windows under these same limits;
it does not add parallelism, unattended scheduling or a larger per-request
window. Stop on the first restriction or failed validation, and preserve
control state on reruns. See the [live check](download-verification.md).

## Scope changes and remaining boundaries

- **Wholesale prices.** SMARD's current data-use notice says that licensing
  questions for wholesale prices are under review in the HEDWIG proceedings.
  The future day-ahead price metric therefore needs a fresh rights review
  before ingestion or redistribution. Do not extend the load-data assessment
  to price data automatically.
- **Other providers.** If a future adapter downloads directly from ENTSO-E
  or another provider, check that provider's terms independently.
- **Personal data.** The current national load fixtures contain time intervals
  and aggregate values, with no identified individuals or households. Any
  later customer, meter or household data needs a separate privacy assessment;
  this note does not cover it.
- **Accuracy and availability.** SMARD disclaims guarantees for completeness,
  accuracy, currency and continuous availability. Retain retrieval dates and
  provenance, and do not describe project outputs as guaranteed or officially
  certified. See the [website terms](https://www.smard.de/home/impressum).
