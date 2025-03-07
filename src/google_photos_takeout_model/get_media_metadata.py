from __future__ import annotations

from asyncio import run
from contextlib import asynccontextmanager
from json import loads
from pathlib import Path
from re import compile
from sys import argv
from typing import AsyncGenerator

from playwright.async_api import Locator, expect
from pydantic import BaseModel, Field
from stamina import retry
from tqdm import tqdm

from google_photos_takeout_model import WAIT, dumps, logged_in
from google_photos_takeout_model.pw import TIMEOUT

GPHOTOS_ALBUM = argv[1] if len(argv) > 1 else ""
ALBUM = Path("album.json")


async def main(album: str = GPHOTOS_ALBUM):
    if not album:
        raise ValueError("Album link required.")
    async with (
        logged_in() as loc,
        album_nav(loc, album) as (alb, nav_count),
    ):
        for _ in tqdm(range(nav_count)):
            alb.media_items.append(await get_media_item_metadata(loc))
            await nav_next(loc)


async def get_media_item_metadata(loc: Locator) -> MediaItemMetadata:
    return MediaItemMetadata(
        item=loc.page.url,
        people=await loc_people(loc).all_inner_texts(),
        albums=await loc_albums_containing_item(loc).all_inner_texts(),
        details=await loc_details(loc).all_inner_texts(),
        position=await get_position(loc),
    )


@asynccontextmanager
async def album_nav(loc: Locator, album: str) -> AsyncGenerator[tuple[Album, int]]:
    await loc.page.goto(album)
    if False and ALBUM.exists():
        prev_album = Album(**loads(ALBUM.read_text(encoding="utf-8")))
        if prev_album.item == loc.page.url:
            alb = prev_album
        else:
            raise ValueError("Album link mismatch.")
    else:
        alb = Album(
            title=(await loc.page.title()).removesuffix(" - Google Photos"),
            item=loc.page.url,
        )
    album_item_count = await get_item_count(loc)
    nav_count = album_item_count - 1
    await nav_first(loc)
    try:
        yield alb, nav_count
    finally:
        ALBUM.write_text(
            encoding="utf-8",
            data=dumps(
                alb.model_dump(),
                indent=2,
                ensure_ascii=False,
            ),
        )


async def nav_first(loc: Locator):
    async with nav(loc):
        await loc_album_media_items(loc).first.click()
        await loc_main(loc).get_by_label("Open info").click()


async def nav_next(loc: Locator):
    async with nav(loc):
        await loc_main(loc).press("ArrowRight")


@asynccontextmanager
async def nav(loc: Locator):
    try:
        async with expect_nav_and_visible_details(loc):
            yield
    except (errors := Exception):
        async with retry(on=errors)(expect_nav_and_visible_details)(loc):
            await loc.page.reload()


@asynccontextmanager
async def expect_nav_and_visible_details(loc: Locator):
    async with loc.page.expect_navigation():
        yield
        await loc.page.wait_for_timeout(WAIT)
    await expect(loc_details(loc).last).to_be_visible(timeout=TIMEOUT)


async def get_image_preview_source(loc: Locator):
    return await loc_image_source(loc).get_attribute("src")


async def get_item_count(loc: Locator) -> int:
    return (
        int(desc.split()[0])
        if (desc := await loc_media_item_count(loc).get_attribute("content"))
        else 0
    )


async def get_position(loc: Locator) -> str:
    return (
        (await loc_position(loc).get_attribute("position") or "")
        if await loc_map(loc).count()
        else ""
    )


async def get_video_source(loc: Locator, details: list[str]) -> str:
    if "(0 B)" in "".join(details):
        return ""
    async with loc.page.expect_download() as downloader:
        await loc.press("Shift+D")
    download = await downloader.value
    await download.cancel()
    download_url = download.url
    return download_url


def loc_albums_containing_item(loc: Locator) -> Locator:
    return loc_info(loc).get_by_role("link", name=compile(r"\d+\sitems"))


def loc_album_media_items(loc: Locator) -> Locator:
    return loc_main(loc).get_by_role("link", name=compile(r"^(?!Back|Goog|Play).*$"))


def loc_details(loc: Locator):
    return loc_info(loc).locator("div").filter(has=loc.page.locator("> dt > svg"))


def loc_image_source(loc):
    return (
        loc_main(loc)
        .filter(has=loc.page.get_by_role("img", name="Photo - "))
        .last.locator("[src]")
    )


def loc_info(loc: Locator) -> Locator:
    return (
        loc_main(loc)
        .locator("c-wiz")
        .filter(has=loc.page.get_by_role("button", name="Close info"))
    )


def loc_media_item_count(loc: Locator) -> Locator:
    loc_desc = "meta[property='og:description'][content*='items added to shared album']"
    return loc.locator(loc_desc)


def loc_main(loc: Locator) -> Locator:
    return loc.get_by_role("main")


def loc_map(loc: Locator) -> Locator:
    return loc.get_by_role("link", name="Map")


def loc_people(loc: Locator) -> Locator:
    return loc_info(loc).get_by_role("link", name="Photo of ")


def loc_position(loc: Locator) -> Locator:
    position = loc_map(loc).locator("[position]").first
    return position


class MediaItemMetadata(BaseModel):
    item: str = ""
    people: list[str] = Field(default_factory=list)
    albums: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)
    position: str = ""


class Album(BaseModel):
    title: str = ""
    item: str = ""
    media_items: list[MediaItemMetadata] = Field(default_factory=list)


if __name__ == "__main__":
    run(main())
