"""Schema definition for ECB EXR daily FX observations."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ECBFxRecord(BaseModel):
    """Single ECB euro reference FX observation (units of currency per 1 EUR)."""

    model_config = ConfigDict(populate_by_name=True)

    observation_date: dt.date
    currency: str
    fx_rate: float
    ingestion_timestamp: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.UTC),
        serialization_alias="_ingestion_timestamp",
    )
    source: str = Field(default="ECB_SDW", serialization_alias="_source")

    @field_validator("observation_date")
    @classmethod
    def validate_observation_date_not_future(cls, value: dt.date) -> dt.date:
        if value > dt.date.today():
            raise ValueError("observation_date must not be in the future")
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a 3-letter ISO 4217 code")
        return normalized

    @field_validator("fx_rate")
    @classmethod
    def validate_fx_rate_positive(cls, value: float) -> float:
        if not (0.0 < value < 1_000_000.0):
            raise ValueError("fx_rate must be positive and within a plausible range")
        return value

    def to_dict(self) -> dict[str, object]:
        """Serialize with model_dump and include underscore aliases."""
        return self.model_dump(by_alias=True)
