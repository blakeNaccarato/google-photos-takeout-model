from pydantic import BaseModel


class GeoData(BaseModel):
    latitude: float
    longitude: float
    altitude: float
    latitudeSpan: float
    longitudeSpan: float


class Time(BaseModel):
    timestamp: str
    formatted: str
