from __future__ import annotations

import re
from asyncio import run
from json import loads
from nt import environ
from pathlib import Path
from sys import argv

from playwright.async_api import Locator, Page
from pydantic import BaseModel, Field
from tqdm import tqdm

from google_photos_takeout_model import dumps, logged_in


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


ALBUM = Path("album.json")


async def main():
    async with logged_in() as pg:
        await get_all_media(pg)


async def get_all_media(pg: Page):
    album_url = argv[1] if len(argv) > 1 else environ["GPHOTOS_ALBUM"]
    m = pg.get_by_role("main")
    loc_desc = "meta[property='og:description'][content*='items added to shared album']"
    await pg.goto(album_url)
    if ALBUM.exists():
        album = Album(**loads(ALBUM.read_text(encoding="utf-8")))
    else:
        album = Album(
            title=(await pg.title()).removesuffix(" - Google Photos"),
            item=pg.url,
        )
        ALBUM.write_text(
            encoding="utf-8",
            data=dumps(
                album.model_dump(),
                indent=2,
                ensure_ascii=False,
            ),
        )
    await pg.get_by_role("link", name=re.compile(r"^(?!Back|Goog).*$")).first.click()
    await m.get_by_label("Open info").click()
    current_media_item = len(album.media_items)
    last_completed_media_item = current_media_item - 1
    for _ in tqdm(range(last_completed_media_item)):
        await nav_next(m)
    media_item_count = (
        int(desc.split()[0])
        if (desc := await pg.locator(loc_desc).get_attribute("content"))
        else 0
    )
    for _ in tqdm(range(last_completed_media_item, media_item_count)):
        await nav_next(m)
        await get_media_item(pg, album)


async def nav_next(m: Locator):
    prev_url = m.page.url
    await m.press("ArrowRight")
    await m.page.wait_for_url(lambda url: url != prev_url)


async def get_media_item(pg: Page, album: Album):
    m = pg.get_by_role("main")
    panes = m.locator("c-wiz")
    # TODO: Detects stale video elements for a few items afterwards.
    # TODO: Use combination of `is_enabled`, `is_visible`, or something to filter down
    # TODO: Not a huge deal, since `Shift+D` points to downloads for pictures as well
    video = panes.nth(1).get_by_title("YouTube Google Photos Video Player")
    info = panes.filter(has=pg.get_by_role("button", name="Close info"))
    position = pg.get_by_role("link", name="Map")
    details = (
        await info.locator("div").filter(has=pg.locator("> dt > svg")).all_inner_texts()
    )
    if "(0 B)" in "".join(details):
        download_url = ""
    elif await video.count():
        async with pg.expect_download() as downloader:
            await m.press("Shift+D")
        download = await downloader.value
        await download.cancel()
        download_url = download.url
    else:
        download_url = await get_css_attr(
            m.filter(has=pg.get_by_role("img", name="Photo - ")).last, "src"
        )
    info.get_by_role("link", name="Photo of ")
    info.get_by_label("File size: ")
    album.media_items.append(
        MediaItem(
            item=pg.url,
            download=re.sub(r"\?authuser=0$", "", download_url),
            people=[
                await iloc.inner_text()
                for iloc in await info.get_by_role("link", name="Photo of ").all()
            ],
            albums=[
                await iloc.inner_text()
                for iloc in await info.get_by_role(
                    "link", name=re.compile(r"\d+\sitems")
                ).all()
            ],
            details=details,
            position=(
                await get_css_attr(position, "position")
                if await position.count()
                else ""
            ),
        )
    )
    ALBUM.write_text(
        encoding="utf-8", data=dumps(album.model_dump(), indent=2, ensure_ascii=False)
    )


async def get_css_attr(locator: Locator, attr: str = "") -> str:
    return await locator.locator(f"[{attr}]").first.get_attribute(attr) or ""


if __name__ == "__main__":
    run(main())
