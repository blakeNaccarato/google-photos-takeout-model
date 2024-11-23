from __future__ import annotations

from json import loads
from pathlib import Path
from re import match
from typing import Annotated as Ann
from typing import Any

from pydantic import BaseModel, Discriminator, Field, Tag
from pydantic.alias_generators import to_snake

from google_photos_takeout_model.models.bases import GeoData, Time, ToCamelBaseModel
from google_photos_takeout_model.models.google_photos_origins import (
    GooglePhotosCompositionOrigin,
    GooglePhotosMobileOrigin,
    GooglePhotosPartnerSharingOrigin,
    GooglePhotosSharedAlbumOrigin,
    GooglePhotosWebOrigin,
)

MEDIA_ITEM_GLOB = "[!metadata]*[!.json]"
PARENTHESIZED_MEDIA_ITEM_STEM = r"(?P<name>^.*[^\s])\((?P<num>\d+)\)$"
NAME_MAX_LENGTH = 51
JSON = ".json"
JSON_STEM_MAX_LENGTH = NAME_MAX_LENGTH - len(JSON)


class Person(ToCamelBaseModel):
    name: str


def discriminate_google_photos_origin(obj: dict[str, Any] | BaseModel) -> str:
    fields = [
        to_snake(field) for field in (obj if isinstance(obj, dict) else dict(obj))
    ]
    match fields:
        case ["composition", *_]:
            return GooglePhotosCompositionOrigin.__name__
        case ["mobile_upload", *_]:
            return GooglePhotosMobileOrigin.__name__
        case ["from_partner_sharing", *_]:
            return GooglePhotosPartnerSharingOrigin.__name__
        case ["from_shared_album", *_]:
            return GooglePhotosSharedAlbumOrigin.__name__
        case ["web_upload", *_]:
            return GooglePhotosWebOrigin.__name__
        case _:
            raise ValueError(f"Can't discriminate GooglePhotosOrigin from {obj}.")


class MediaItem(ToCamelBaseModel):
    path: Path
    metadata_path: Path
    title: str
    description: str
    image_views: str
    creation_time: Time
    photo_taken_time: Time
    geo_data: GeoData
    geo_data_exif: GeoData
    people: list[Person] = Field(default_factory=list)
    url: str
    google_photos_origin: (
        Ann[
            Ann[
                GooglePhotosCompositionOrigin,
                Tag(GooglePhotosCompositionOrigin.__name__),
            ]
            | Ann[GooglePhotosMobileOrigin, Tag(GooglePhotosMobileOrigin.__name__)]
            | Ann[
                GooglePhotosPartnerSharingOrigin,
                Tag(GooglePhotosPartnerSharingOrigin.__name__),
            ]
            | Ann[
                GooglePhotosSharedAlbumOrigin,
                Tag(GooglePhotosSharedAlbumOrigin.__name__),
            ]
            | Ann[GooglePhotosWebOrigin, Tag(GooglePhotosWebOrigin.__name__)],
            Discriminator(discriminate_google_photos_origin),
        ]
        | None
    ) = None

    @classmethod
    def from_path(cls, path: Path) -> MediaItem:
        # sourcery skip: merge-else-if-into-elif, remove-pass-elif
        if (metadata_path := path.with_name(f"{path.name}.json")).exists():
            pass
        elif (metadata_path := path.with_name(f"{path.name}.jpg.json")).exists():
            pass
        elif (metadata_path := path.with_name(f"{path.stem}.json")).exists():
            pass
        elif (metadata_path := path.with_name(f"{path.stem}.jpg.json")).exists():
            pass
        else:
            if path.stem.endswith("-edited"):
                metadata_path = path.with_name(
                    f"{path.stem.removesuffix("-edited")}{path.suffix}.json"
                )
            elif len(path.name) > JSON_STEM_MAX_LENGTH:
                metadata_path = path.with_name(
                    f"{path.name[:JSON_STEM_MAX_LENGTH]}{JSON}"
                )
            elif stem := match(PARENTHESIZED_MEDIA_ITEM_STEM, path.stem):
                if (
                    metadata_path := path.with_name(
                        f"{stem["name"]}{path.suffix}({stem["num"]}).json"
                    )
                ).exists():
                    pass
                elif (
                    metadata_path := path.with_name(
                        f"{stem["name"]}{path.suffix}.jpg({stem["num"]}).json"
                    )
                ).exists():
                    pass
            else:
                raise ValueError(f"Can't get metadata path from {path}.")
            if not metadata_path.exists():
                raise ValueError(f"Metadata file for {path} does not exist.")
        return cls.model_validate(
            obj={
                "path": path,
                "metadata_path": metadata_path,
                **loads(metadata_path.read_text(encoding="utf-8")),
            }
        )


def get_media_items(path: Path) -> list[MediaItem]:
    return [MediaItem.from_path(path) for path in path.glob(MEDIA_ITEM_GLOB)]
