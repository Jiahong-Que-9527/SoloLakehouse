"""GCP BigQuery adapter (plan Task 2.1).

Lazy imports like G01's adapters so the core package and its tests run
without the cloud extra. The view is the only sanctioned data surface:
release resolution reads the view, never the G01 ledger table, because
the runtime identity holds dataViewer on the view alone. Every query is
parameterised, capped by maximum_bytes_billed and bounded by a result
timeout; platform failures translate to ValidationError(query_rejected)
so the app fails closed.
"""

import concurrent.futures
from datetime import UTC, datetime

from energy_api.guards import QueryGuard, ValidationError
from energy_api.model import Observation, Summary

_FETCH_SQL = (
    "SELECT interval_start, interval_end, area, metric, value, unit, release_id\n"
    "FROM `{table}`\n"
    "WHERE metric = @metric AND area = @area AND release_id = @release_id\n"
    "  AND interval_start >= @start AND interval_start < @end\n"
    "ORDER BY interval_start"
)
_RESOLVE_SQL = (
    "SELECT release_id, MAX(ingested_at) AS latest\n"
    "FROM `{table}`\n"
    "WHERE metric = @metric\n"
    "GROUP BY release_id\n"
    "ORDER BY latest DESC\n"
    "LIMIT 1"
)
_SUMMARIZE_SQL = (
    "SELECT COUNT(*) AS n, MIN(value) AS lo, MAX(value) AS hi\n"
    "FROM `{table}`\n"
    "WHERE metric = @metric AND area = @area AND release_id = @release_id\n"
    "  AND interval_start >= @start AND interval_start < @end"
)


class GcpQueryLayer:
    """BigQuery-backed QueryPort over the authorized view."""

    def __init__(
        self,
        dataset: str = "energy_api",
        view: str = "metric_observation",
        guard: QueryGuard | None = None,
        client=None,
    ) -> None:
        self._dataset = dataset
        self._view = view
        self._guard = guard or QueryGuard()
        self._client = client

    def _bq(self):
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client()
        return self._client

    def _table(self) -> str:
        return f"{self._bq().project}.{self._dataset}.{self._view}"

    def _param(self, name: str, type_: str, value):
        from google.cloud import bigquery

        return bigquery.ScalarQueryParameter(name, type_, value)

    def _run(self, sql: str, params: list) -> list:
        from google.cloud import bigquery

        try:
            from google.api_core.exceptions import BadRequest
        except ImportError:  # pragma: no cover - only when the extra is missing

            class BadRequest(Exception):
                pass

        config = bigquery.QueryJobConfig(query_parameters=params)
        config.maximum_bytes_billed = self._guard.max_bytes_billed
        try:
            job = self._bq().query(sql, job_config=config)
            rows = list(job.result(timeout=self._guard.timeout_seconds))
        except concurrent.futures.TimeoutError as exc:
            message = f"query exceeded {self._guard.timeout_seconds}s"
            raise ValidationError(code="query_rejected", message=message) from exc
        except BadRequest as exc:
            message = "query rejected by the configured guard"
            raise ValidationError(code="query_rejected", message=message) from exc
        return rows

    def resolve_release(self, metric: str) -> str | None:
        sql = _RESOLVE_SQL.format(table=self._table())
        rows = self._run(sql, [self._param("metric", "STRING", metric)])
        return rows[0]["release_id"] if rows else None

    def fetch_observations(
        self,
        metric: str,
        area: str,
        start: datetime,
        end: datetime,
        release_id: str,
    ) -> list[Observation]:
        sql = _FETCH_SQL.format(table=self._table())
        rows = self._run(
            sql,
            [
                self._param("metric", "STRING", metric),
                self._param("area", "STRING", area),
                self._param("release_id", "STRING", release_id),
                self._param("start", "TIMESTAMP", start),
                self._param("end", "TIMESTAMP", end),
            ],
        )
        return [
            Observation(
                interval_start=row["interval_start"].astimezone(UTC),
                interval_end=row["interval_end"].astimezone(UTC),
                area=row["area"],
                metric=row["metric"],
                value=row["value"],
                unit=row["unit"],
                release_id=row["release_id"],
            )
            for row in rows
        ]

    def summarize(
        self,
        metric: str,
        area: str,
        start: datetime,
        end: datetime,
        release_id: str,
    ) -> Summary:
        sql = _SUMMARIZE_SQL.format(table=self._table())
        rows = self._run(
            sql,
            [
                self._param("metric", "STRING", metric),
                self._param("area", "STRING", area),
                self._param("release_id", "STRING", release_id),
                self._param("start", "TIMESTAMP", start),
                self._param("end", "TIMESTAMP", end),
            ],
        )
        if not rows:
            return Summary(count=0, minimum=None, maximum=None, unit="MWh")
        return Summary(
            count=rows[0]["n"],
            minimum=rows[0]["lo"],
            maximum=rows[0]["hi"],
            unit="MWh",
        )
