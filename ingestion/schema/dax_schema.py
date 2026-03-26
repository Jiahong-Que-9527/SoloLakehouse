"""Schema definition for DAX daily OHLCV observations."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DAXRecord(BaseModel):
    """Single DAX daily OHLCV record."""

    model_config = ConfigDict(populate_by_name=True)

    observation_date: dt.date
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    ingestion_timestamp: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.UTC),
        serialization_alias="_ingestion_timestamp",
    )
    source: str = Field(default="DAX_SAMPLE", serialization_alias="_source")

    @field_validator("observation_date")
    @classmethod
    def validate_observation_date_not_future(cls, value: dt.date) -> dt.date:
        if value > dt.date.today():
            raise ValueError("observation_date must not be in the future")
        return value

    @field_validator("open_price", "close_price")
    @classmethod
    def validate_positive_prices(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("open_price and close_price must be > 0")
        return value

    @model_validator(mode="after")
    def validate_high_low(self) -> "DAXRecord":
        if self.high_price < self.low_price:
            raise ValueError("high_price must be >= low_price")
        return self
