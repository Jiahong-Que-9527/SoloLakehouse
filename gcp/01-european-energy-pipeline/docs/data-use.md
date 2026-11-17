# Data use and compliance

Reviewed on 2026-11-17 against the provider's public terms. This note covers
German actual total load from SMARD (`moduleIds: [5000410]`, region `DE`).
It records the basis for the planned implementation; automated acquisition
and publication are not implemented yet. Recheck the terms when adding a
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

For the planned live adapter, use low concurrency, cache successful downloads,
request bounded windows and use bounded retries with backoff. Respect HTTP
429 and any `Retry-After` response; stop on persistent access denial rather
than bypassing controls. These are project operating practices to limit load,
not a claim that SMARD specifies those exact mechanisms. Reassess provider
guidance before substantially increasing request volume.

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
