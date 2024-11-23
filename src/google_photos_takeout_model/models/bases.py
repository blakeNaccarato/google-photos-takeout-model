"""Base models."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ToCamelBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validation_error_cause=True,
        populate_by_name=True,
    )


class GeoData(ToCamelBaseModel):
    latitude: float
    longitude: float
    altitude: float
    latitude_span: float
    longitude_span: float


class Time(ToCamelBaseModel):
    timestamp: str
    formatted: str
