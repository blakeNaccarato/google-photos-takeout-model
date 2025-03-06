from __future__ import annotations

from asyncio import run
from json import loads
from pathlib import Path
from re import compile
from sys import argv

from playwright.async_api import Locator, Page
from pydantic import BaseModel, Field
from tqdm import tqdm

from google_photos_takeout_model import dumps, logged_in

GPHOTOS_ALBUM = argv[1] if len(argv) > 1 else ""
ALBUM = Path("album.json")


async def main():
    async with logged_in() as pg:
        await get_all_media(pg)


async def get_all_media(pg: Page, album: str = GPHOTOS_ALBUM):
    if not album:
        raise ValueError("Album link required.")
    await pg.goto(album)
    if ALBUM.exists():
        alb = Album(**loads(ALBUM.read_text(encoding="utf-8")))
    else:
        alb = Album(
            title=(await pg.title()).removesuffix(" - Google Photos"),
            item=pg.url,
        )
        ALBUM.write_text(
            encoding="utf-8",
            data=dumps_album(alb),
        )
    await nav_first(pg)
    pg_main = pg.get_by_role("main")
    await pg_main.get_by_label("Open info").click()
    album_item_count = await get_item_count(pg)
    current_media_item = len(alb.media_items)
    for _ in tqdm(range(1, current_media_item)):
        await nav_next(pg_main)
    for _ in tqdm(range(current_media_item, album_item_count)):
        await nav_next(pg_main)
        await get_media_item(pg, alb)


async def get_media_item(pg: Page, album: Album):
    pg_main = pg.get_by_role("main")
    info = pg_main.locator("c-wiz").filter(
        has=pg.get_by_role("button", name="Close info")
    )
    all_details = (
        await info.locator("div").filter(has=pg.locator("> dt > svg")).all_inner_texts()
    )
    download = (
        "" if "(0 B)" in "".join(all_details) else await get_download_url(pg, pg_main)
    ).removesuffix("authuser=0")
    map = pg.get_by_role("link", name="Map")
    position = map.locator("[position]").first.get_attribute("position")
    people = info.get_by_role("link", name="Photo of ")
    albums = info.get_by_role("link", name=compile(r"\d+\sitems"))
    album.media_items.append(
        MediaItem(
            item=pg.url,
            download=download,
            people=await people.all_inner_texts(),
            albums=await albums.all_inner_texts(),
            details=all_details,
            position=(await position or "") if await map.count() else "",
        )
    )
    ALBUM.write_text(encoding="utf-8", data=dumps_album(album))


def dumps_album(album: Album) -> str:
    return dumps(
        album.model_dump(),
        indent=2,
        ensure_ascii=False,
    )


async def get_item_count(pg: Page) -> int:
    loc_desc = "meta[property='og:description'][content*='items added to shared album']"
    return (
        int(desc.split()[0])
        if (desc := await pg.locator(loc_desc).get_attribute("content"))
        else 0
    )


async def get_download_url(pg: Page, loc: Locator) -> str:
    async with pg.expect_download() as downloader:
        await loc.press("Shift+D")
    download = await downloader.value
    await download.cancel()
    download_url = download.url
    return download_url


async def nav_first(pg: Page):
    await pg.get_by_role("link", name=compile(r"^(?!Back|Goog).*$")).first.click()


async def nav_next(loc: Locator):
    prev_url = loc.page.url
    await loc.press("ArrowRight")
    await loc.page.wait_for_url(lambda url: url != prev_url)


class MediaItem(BaseModel):
    item: str = ""
    download: str = ""
    people: list[str] = Field(default_factory=list)
    albums: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)
    position: str = ""


class Album(BaseModel):
    title: str = ""
    item: str = ""
    media_items: list[MediaItem] = Field(default_factory=list)


if __name__ == "__main__":
    run(main())
