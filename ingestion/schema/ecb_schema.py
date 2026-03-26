"""Schema definition for ECB MRO observations."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ECBRecord(BaseModel):
    """Single ECB MRO rate observation."""

    model_config = ConfigDict(populate_by_name=True)

    observation_date: dt.date
    rate_pct: float
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

    @field_validator("rate_pct")
    @classmethod
    def validate_rate_pct_range(cls, value: float) -> float:
        if not -5.0 <= value <= 20.0:
            raise ValueError("rate_pct must be between -5.0 and 20.0")
        return value

    def to_dict(self) -> dict[str, object]:
        """Serialize with model_dump and include underscore aliases."""
        return self.model_dump(by_alias=True)


EcbObservation = ECBRecord
