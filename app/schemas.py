from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InstrumentRead(BaseModel):
    id: int
    name: str
    label: int
    unit: str
    min_value: float
    max_value: float

    model_config = ConfigDict(from_attributes=True)


class ShipmentWrite(BaseModel):
    instrument_id: int = Field(gt=0)
    value: float


class ShipmentRead(BaseModel):
    id: int
    instrument_id: int
    instrument_name: str
    unit: str
    value: float
    min_value: float
    max_value: float
    arinc_word: int
    arinc_hex: str
    created_at: datetime | None
    transmitted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
