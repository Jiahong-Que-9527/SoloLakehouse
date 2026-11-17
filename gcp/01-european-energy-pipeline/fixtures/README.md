# SMARD fixtures

Unmodified CSV exports of German actual total load, downloaded on 2026-11-15.
The bytes are the download response. They were not re-encoded or edited.

Source: [SMARD download centre](https://www.smard.de/home/downloadcenter/download-marktdaten),
the same export as **Datei herunterladen**. Request:
`POST https://www.smard.de/nip-download-manager/nip/download/market-data`
with `moduleIds` `[5000410]` (Realisierter Stromverbrauch, Gesamt / Netzlast),
`region` `DE`, `resolution` `quarterhour`, `format` `CSV`, `language` `de`.

Attribution: Bundesnetzagentur | SMARD.de. The market-data download is published
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
See the provider's [data-use notice](https://www.smard.de/home/datennutzung)
and the project's [data use and compliance note](../docs/data-use.md) for
redistribution, attribution and automated-download requirements. The data
licence is separate from the repository's software licence.

| | Normal week | Local-time change |
|---|---|---|
| File | `Realisierter_Stromverbrauch_202606080000_202606150000_Viertelstunde.csv` | `Realisierter_Stromverbrauch_202610250000_202610260000_Viertelstunde.csv` |
| Window, Europe/Berlin | 2026-06-08 00:00 inclusive to 2026-06-15 00:00 exclusive | 2026-10-25 00:00 inclusive to 2026-10-26 00:00 exclusive |
| Data rows | 672 | 100 |
| SHA-256 | `d08c74c385656bf2eb5d02da208dd31861cf435353cee869f98b8f6665771ee6` | `eed51b2a912c41af7d907d8cfd0aec7d6c031ac946c2e1ea0441460ec60d9edb` |

Both files are UTF-8 with a BOM, CRLF, and semicolon-separated. The header is
`Datum von;Datum bis;Netzlast [MWh] Originalauflösungen`. Timestamps are local
civil time with no offset and no marker for the repeated hour. Numbers use a
dot as the thousands separator and a comma as the decimal mark. The value is
energy in that quarter hour, MWh. Original resolution is 15 minutes.

On 2026-10-25 the labels `02:00`, `02:15`, `02:30` and `02:45` each occur
twice, with different values. The first run of that hour is still CEST
(UTC+2). The second is CET (UTC+1). The week file has no repeated local start.
