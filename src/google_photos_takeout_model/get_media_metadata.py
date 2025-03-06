from __future__ import annotations

from asyncio import run
from contextlib import asynccontextmanager
from pathlib import Path
from re import compile
from sys import argv
from typing import AsyncGenerator

from playwright.async_api import Locator, Page
from pydantic import BaseModel, Field
from tqdm import tqdm

from google_photos_takeout_model import dumps, logged_in

GPHOTOS_ALBUM = argv[1] if len(argv) > 1 else ""
ALBUM = Path("album.json")


async def main(album: str = GPHOTOS_ALBUM):
    if not album:
        raise ValueError("Album link required.")
    async with logged_in() as pg, album_nav(pg, album) as (alb, nav_count):
        for _ in tqdm(range(nav_count)):
            await get_media_metadata(pg, alb)


async def get_media_metadata(pg: Page, album: Album):
    await nav_next(pg)
    album.media_items.append(
        MediaItem(
            item=pg.url,
            people=await loc_people(pg).all_inner_texts(),
            albums=await loc_albums_containing_item(pg).all_inner_texts(),
            details=await loc_details(pg).all_inner_texts(),
            position=await get_position(pg),
        )
    )


@asynccontextmanager
async def album_nav(pg: Page, album: str) -> AsyncGenerator[tuple[Album, int]]:
    await pg.goto(album)
    alb = Album(
        title=(await pg.title()).removesuffix(" - Google Photos"),
        item=pg.url,
    )
    await nav_first(pg)
    await loc_main(pg).get_by_label("Open info").click()
    album_item_count = await get_item_count(pg)
    nav_count = album_item_count - 1
    try:
        yield alb, nav_count
    finally:
        ALBUM.write_text(encoding="utf-8", data=album_dumps(alb))


def loc_albums_containing_item(loc: Locator | Page) -> Locator:
    return loc_info(loc).get_by_role("link", name=compile(r"\d+\sitems"))


def loc_people(loc: Locator | Page) -> Locator:
    return loc_info(loc).get_by_role("link", name="Photo of ")


def album_dumps(album: Album) -> str:
    return dumps(
        album.model_dump(),
        indent=2,
        ensure_ascii=False,
    )


async def get_item_count(pg: Page) -> int:
    return (
        int(desc.split()[0])
        if (desc := await loc_item_count(pg).get_attribute("content"))
        else 0
    )


async def get_position(loc: Locator | Page) -> str:
    return (
        (await loc_position(loc).get_attribute("position") or "")
        if await loc_map(loc).count()
        else ""
    )


async def nav_first(pg: Page):
    async with nav(pg):
        await loc_album_items(pg).first.click()


async def nav_next(pg: Page):
    async with nav(pg):
        await pg.locator("body").press("ArrowRight")


@asynccontextmanager
async def nav(pg: Page):
    async with pg.expect_navigation():
        yield


def loc_album_items(loc: Locator | Page) -> Locator:
    return loc_main(loc).get_by_role("link", name=compile(r"^(?!Back|Goog).*$"))


def loc_details(loc: Locator | Page):
    return loc_info(loc).locator("div").filter(has=loc.locator("> dt > svg"))


def loc_info(loc: Locator | Page) -> Locator:
    return (
        loc_main(loc)
        .locator("c-wiz")
        .filter(has=loc.get_by_role("button", name="Close info"))
    )


def loc_item_count(loc: Locator | Page) -> Locator:
    loc_desc = "meta[property='og:description'][content*='items added to shared album']"
    return loc.locator(loc_desc)


def loc_main(loc: Locator | Page) -> Locator:
    return loc.get_by_role("main")


def loc_map(loc: Locator | Page) -> Locator:
    return loc.get_by_role("link", name="Map")


def loc_position(loc: Locator | Page) -> Locator:
    position = loc_map(loc).locator("[position]").first
    return position


class MediaItem(BaseModel):
    item: str = ""
    people: list[str] = Field(default_factory=list)
    albums: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)
    position: str = ""


class Album(BaseModel):
    title: str = ""
    item: str = ""
    media_items: list[MediaItem] = Field(default_factory=list)


async def get_image_preview_url(pg: Page):
    return (
        await loc_main(pg)
        .filter(has=pg.get_by_role("img", name="Photo - "))
        .last.locator("[src]")
        .get_attribute("src")
    )


async def get_url(loc: Locator) -> str:
    if "(0 B)" in "".join(await loc_details(loc).all_inner_texts()):
        return ""
    pg = loc.page
    async with pg.expect_download() as downloader:
        await loc.press("Shift+D")
    download = await downloader.value
    await download.cancel()
    download_url = download.url
    return download_url


if __name__ == "__main__":
    run(main())
