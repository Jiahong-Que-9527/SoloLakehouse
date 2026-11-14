"""Configuration loading and validation."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml

DEFAULT_CONFIG_NAME = "dataset.eddf_r75km.v1.yaml"


class ConfigError(ValueError):
    """The configuration file is missing values or contains invalid ones."""


@dataclass(frozen=True)
class BBox:
    south: float
    north: float
    west: float
    east: float

    def validate(self) -> None:
        if not (-90 <= self.south < self.north <= 90):
            raise ConfigError("bbox latitude range is invalid")
        if not (-180 <= self.west < self.east <= 180):
            raise ConfigError("bbox longitude range is invalid")


@dataclass(frozen=True)
class SourceConfig:
    host: str
    port: int
    catalog: str
    schema: str
    query_timeout_seconds: int
    login_timeout_seconds: int

    def table(self, name: str) -> str:
        return f"{self.catalog}.{self.schema}.{name}"


@dataclass(frozen=True)
class PathsConfig:
    data_root: Path
    backup_root: Path
    token_dir: Path


@dataclass(frozen=True)
class RegionConfig:
    id: str
    version: str
    airport: str
    latitude: float
    longitude: float
    radius_km: float
    bbox: BBox


@dataclass(frozen=True)
class PeriodConfig:
    start: date
    end: date  # exclusive

    @property
    def hours(self) -> int:
        return int((self.end - self.start).days) * 24

    @property
    def days(self) -> int:
        return int((self.end - self.start).days)


@dataclass(frozen=True)
class StateVectorsConfig:
    table: str
    columns: tuple[str, ...]
    optional_columns: tuple[str, ...]


@dataclass(frozen=True)
class FlightsConfig:
    table: str
    dataset_id: str
    version: str
    day_end: date  # exclusive


@dataclass(frozen=True)
class DiscoveryConfig:
    hour_probes: tuple[datetime, ...]
    rowcount_probe_hours: tuple[datetime, ...]
    flight_probe_days: tuple[date, ...]


@dataclass(frozen=True)
class Config:
    source: SourceConfig
    paths: PathsConfig
    region: RegionConfig
    period: PeriodConfig
    state_vectors: StateVectorsConfig
    flights: FlightsConfig
    discovery: DiscoveryConfig

    @property
    def username(self) -> str:
        name = os.environ.get("OPENSKY_USERNAME", "").strip().lower()
        if not name:
            raise ConfigError("OPENSKY_USERNAME is not set")
        return name


def _require(mapping: dict, key: str, where: str):
    if not isinstance(mapping, dict) or key not in mapping:
        raise ConfigError(f"missing '{key}' in {where}")
    return mapping[key]


def _path(env_name: str, configured: str) -> Path:
    return Path(os.environ.get(env_name) or configured).expanduser()


def _day(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ConfigError(f"invalid date: {value!r}") from exc


def _hour(value) -> datetime:
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ConfigError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    parsed = parsed.astimezone(UTC)
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ConfigError(f"timestamp is not on an hour boundary: {value!r}")
    return parsed


def default_config_path() -> Path:
    env = os.environ.get("OPENSKY_INGEST_CONFIG")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parents[2] / "configs" / DEFAULT_CONFIG_NAME


def load_config(path: Path | str | None = None) -> Config:
    config_path = Path(path) if path else default_config_path()
    try:
        raw = yaml.safe_load(config_path.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {config_path}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")

    source = _require(raw, "source", "config")
    paths = _require(raw, "paths", "config")
    region = _require(raw, "region", "config")
    period = _require(raw, "period", "config")
    sv = _require(raw, "state_vectors", "config")
    fl = _require(raw, "flights", "config")
    disc = _require(raw, "discovery", "config")
    bbox = _require(region, "bbox", "region")
    center = _require(region, "center", "region")

    cfg = Config(
        source=SourceConfig(
            host=_require(source, "host", "source"),
            port=int(_require(source, "port", "source")),
            catalog=_require(source, "catalog", "source"),
            schema=_require(source, "schema", "source"),
            query_timeout_seconds=int(_require(source, "query_timeout_seconds", "source")),
            login_timeout_seconds=int(_require(source, "login_timeout_seconds", "source")),
        ),
        paths=PathsConfig(
            data_root=_path("SLH_DATA_ROOT", _require(paths, "data_root", "paths")),
            backup_root=_path("SLH_BACKUP_ROOT", _require(paths, "backup_root", "paths")),
            token_dir=_path("SLH_TOKEN_DIR", _require(paths, "token_dir", "paths")),
        ),
        region=RegionConfig(
            id=_require(region, "id", "region"),
            version=_require(region, "version", "region"),
            airport=_require(region, "airport", "region"),
            latitude=float(_require(center, "latitude", "region.center")),
            longitude=float(_require(center, "longitude", "region.center")),
            radius_km=float(_require(region, "radius_km", "region")),
            bbox=BBox(
                south=float(_require(bbox, "south", "region.bbox")),
                north=float(_require(bbox, "north", "region.bbox")),
                west=float(_require(bbox, "west", "region.bbox")),
                east=float(_require(bbox, "east", "region.bbox")),
            ),
        ),
        period=PeriodConfig(
            start=_day(_require(period, "start", "period")),
            end=_day(_require(period, "end", "period")),
        ),
        state_vectors=StateVectorsConfig(
            table=_require(sv, "table", "state_vectors"),
            columns=tuple(_require(sv, "columns", "state_vectors")),
            optional_columns=tuple(sv.get("optional_columns") or ()),
        ),
        flights=FlightsConfig(
            table=_require(fl, "table", "flights"),
            dataset_id=_require(fl, "dataset_id", "flights"),
            version=_require(fl, "version", "flights"),
            day_end=_day(_require(fl, "day_end", "flights")),
        ),
        discovery=DiscoveryConfig(
            hour_probes=tuple(_hour(v) for v in _require(disc, "hour_probes", "discovery")),
            rowcount_probe_hours=tuple(
                _hour(v) for v in _require(disc, "rowcount_probe_hours", "discovery")
            ),
            flight_probe_days=tuple(
                _day(v) for v in _require(disc, "flight_probe_days", "discovery")
            ),
        ),
    )
    validate(cfg)
    return cfg


def validate(cfg: Config) -> None:
    cfg.region.bbox.validate()
    if cfg.period.end <= cfg.period.start:
        raise ConfigError("period end must be after start")
    if cfg.flights.day_end != cfg.period.end + timedelta(days=1):
        raise ConfigError("flights day_end must be one day after the period end")
    if len(set(cfg.state_vectors.columns)) != len(cfg.state_vectors.columns):
        raise ConfigError("state_vectors columns contain duplicates")
    for required in ("time", "icao24", "lat", "lon", "hour"):
        if required not in cfg.state_vectors.columns:
            raise ConfigError(f"state_vectors columns must include '{required}'")
    if not re.fullmatch(r"[A-Z]{4}", cfg.region.airport):
        raise ConfigError("airport must be a four-letter ICAO code")
    if cfg.region.radius_km <= 0:
        raise ConfigError("radius_km must be positive")
