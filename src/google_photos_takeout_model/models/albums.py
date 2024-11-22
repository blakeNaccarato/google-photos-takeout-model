from __future__ import annotations

from json import loads
from pathlib import Path

from pydantic import BaseModel, Field

from google_photos_takeout_model.models import GeoData, Time
from google_photos_takeout_model.models.media_items import MediaItem, get_media_items

ALBUM_METADATA = "metadata.json"


class Album(BaseModel):
    path: Path
    metadata_path: Path
    media_items: list[MediaItem] = Field(default_factory=list)

    title: str
    description: str
    access: str
    date: Time
    location: str
    geoData: GeoData

    @classmethod
    def from_path(cls, path: Path) -> Album:
        return cls.model_validate(
            obj={
                "path": path,
                "metadata_path": path / ALBUM_METADATA,
                "media_items": get_media_items(path),
                **loads((path / ALBUM_METADATA).read_text(encoding="utf-8")),
            }
        )
