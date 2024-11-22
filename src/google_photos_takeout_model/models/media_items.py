from __future__ import annotations

from json import loads
from pathlib import Path
from re import match
from typing import TypedDict

from pydantic import BaseModel, Field

from google_photos_takeout_model.models import GeoData, Time

MEDIA_ITEM_GLOB = "[!metadata]*[!.json]"
PARENTHESIZED_MEDIA_ITEM_STEM = r"(?P<name>^.*[^\s])\((?P<num>\d+)\)$"
NAME_MAX_LENGTH = 51
JSON_SUFFIX = ".json"
JSON_STEM_MAX_LENGTH = NAME_MAX_LENGTH - len(JSON_SUFFIX)


class EmptyDict(TypedDict): ...


class DeviceFolder(BaseModel):
    localFolderName: str


class Composition(BaseModel):
    type: str


class GooglePhotosCompositionOrigin(BaseModel):
    composition: Composition


class MobileUpload(BaseModel):
    deviceFolder: DeviceFolder
    deviceType: str


class GooglePhotosMobileOrigin(BaseModel):
    mobileUpload: MobileUpload | EmptyDict


class GooglePhotosPartnerSharingOrigin(BaseModel):
    fromPartnerSharing: EmptyDict


class GooglePhotosSharedAlbumOrigin(BaseModel):
    fromSharedAlbum: EmptyDict


class WebUpload(BaseModel):
    computerUpload: EmptyDict


class GooglePhotosWebOrigin(BaseModel):
    webUpload: WebUpload


class Person(BaseModel):
    name: str


class MediaItem(BaseModel):
    path: Path
    metadata_path: Path
    title: str
    description: str
    imageViews: str
    creationTime: Time
    photoTakenTime: Time
    geoData: GeoData
    geoDataExif: GeoData
    people: list[Person] = Field(default_factory=list)
    url: str
    googlePhotosOrigin: (
        GooglePhotosCompositionOrigin
        | GooglePhotosMobileOrigin
        | GooglePhotosPartnerSharingOrigin
        | GooglePhotosSharedAlbumOrigin
        | GooglePhotosWebOrigin
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
                    f"{path.name[:JSON_STEM_MAX_LENGTH]}{JSON_SUFFIX}"
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
