from __future__ import annotations

from asyncio import TaskGroup, run
from concurrent.futures import InvalidStateError
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from json import loads
from pathlib import Path
from re import compile
from sys import argv
from typing import Any, AsyncGenerator, Callable, Coroutine, Literal, TypeAlias

import stamina
from playwright.async_api import Locator, TimeoutError, expect
from pydantic import BaseModel, Field
from tqdm import tqdm

from google_photos_takeout_model import WAIT, dumps
from google_photos_takeout_model.pw import (
    NAV_TIMEOUT,
    STORAGE_STATE,
    TIMEOUT,
    locator,
    logged_in,
)

StringProcessor: TypeAlias = Callable[[str, Locator], Coroutine[Any, Any, None]]


retry_on = (AssertionError, InvalidStateError, RuntimeError, TimeoutError)
retry = stamina.retry(on=retry_on, attempts=10_000, timeout=50_000)

GPHOTOS_ALBUM = argv[1] if len(argv) > 1 else ""
ALBUM = Path("album.json")


async def main():
    await process_strings(f=get_media_metadata, strings=argv[1:])


async def process_strings(f: StringProcessor, strings: list[str]):
    async with logged_in() as loc:
        await loc_main(loc).get_by_role("link", name="Photo - ").first.click()
        async with wait(loc, "before"):
            if not await loc_info(loc).is_visible():
                await loc_main(loc).press("i")
        await loc.page.context.storage_state(path=STORAGE_STATE)
    async with TaskGroup() as tg:
        for string in strings:
            tg.create_task(process_string(f, string))


async def process_string(f: StringProcessor, string: str):
    async with locator() as loc:
        await f(string, loc)


async def get_media_metadata(album: str, loc: Locator):
    async with album_nav(loc, album) as (alb, finished_nav_count, nav_count):
        for _ in tqdm(range(finished_nav_count, nav_count)):
            async with nav_next_after(loc):
                alb.media_items_metadata.append(await get_media_item_metadata(loc))


async def get_media_item_metadata(loc: Locator) -> MediaItemMetadata:
    albums = await loc_albums_containing_item(loc).all_inner_texts()
    while not albums:
        async with logged_in():
            pass
        await loc.page.context.storage_state(path=STORAGE_STATE)
    return MediaItemMetadata(
        item=loc.page.url,
        people=await loc_people(loc).all_inner_texts(),
        albums=albums,
        details=await loc_details(loc).all_inner_texts(),
        position=await get_position(loc),
    )


@asynccontextmanager
async def album_nav(loc: Locator, album: str) -> AsyncGenerator[tuple[Album, int, int]]:
    await loc.page.goto(album)
    title = (await loc.page.title()).removesuffix(" - Google Photos")
    album_path = Path(f"{title}.json")
    if album_path.exists():
        alb = Album(**loads(album_path.read_text(encoding="utf-8")))
    else:
        alb = Album(
            title=title,
            item=loc.page.url,
        )
    finished_album_item_count = len(alb.media_items_metadata)
    finished_nav_count = finished_album_item_count - 1
    album_item_count = await get_item_count(loc)
    nav_count = album_item_count - 1
    await (
        nav_first_unfinished(loc, url=alb.media_items_metadata[-1].item)
        if finished_album_item_count
        else nav_first(loc)
    )
    try:
        yield alb, finished_nav_count, nav_count
    finally:
        album_path.write_text(
            encoding="utf-8",
            data=dumps(
                alb.model_dump(),
                indent=2,
                ensure_ascii=False,
            ),
        )


async def nav_first(loc: Locator):
    async with reload_on_retry(loc, loc.page.expect_navigation, timeout=NAV_TIMEOUT):
        await loc_album_media_items(loc).first.click()
    async with reload_on_retry(loc, expect_details, loc):
        pass


async def nav_first_unfinished(loc: Locator, url: str):
    await loc.page.goto(url)
    async with wait(loc, "before"), wait(loc, "after"):
        await nav_next(loc)


@asynccontextmanager
async def nav_next_after(loc: Locator):
    async with wait(loc, "after"):
        yield
        nav_next(loc)


async def nav_next(loc: Locator):
    async with reload_on_retry(loc, loc.page.expect_navigation, timeout=NAV_TIMEOUT):
        await retry(loc_main(loc).press)("ArrowRight")
    async with reload_on_retry(loc, expect_details, loc):
        pass


@asynccontextmanager
async def expect_details(loc: Locator):
    async with wait(loc, "before"):
        yield
    await expect(loc_details(loc).last).to_be_visible(timeout=TIMEOUT)


@asynccontextmanager
async def wait(loc: Locator, kind: Literal["before", "after"]):
    if kind == "before":
        await loc.page.wait_for_timeout(WAIT)
    yield
    if kind == "after":
        await loc.page.wait_for_timeout(WAIT)


@asynccontextmanager
async def reload_on_retry(
    loc: Locator,
    context: Callable[..., AbstractAsyncContextManager[Any]],
    *args,
    **kwds,
):
    try:
        async with context(*args, **kwds):
            yield
    except retry_on:
        async with retry(context)(*args, **kwds):
            await loc.page.reload()


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
        (await map.locator("[position]").first.get_attribute("position") or "")
        if await (map := loc_map(loc)).count()
        else ""
    )


async def get_video_source(loc: Locator, details: list[str]) -> str:
    if "(0 B)" in "".join(details):
        return ""
    async with loc.page.expect_download() as downloader:
        await retry(loc.press)("Shift+D")
    download = await downloader.value
    await download.cancel()
    return download.url


def loc_albums_containing_item(loc: Locator) -> Locator:
    return loc_info(loc).get_by_role("link", name=compile(r"\d+\sitems"))


def loc_album_media_items(loc: Locator) -> Locator:
    return loc_main(loc).get_by_role("link", name=compile(r"^(?!Back|Goog|Play).*$"))


def loc_details(loc: Locator):
    return loc_info(loc).locator("div").filter(has=loc.page.locator("> dt > svg"))


def loc_image_source(loc: Locator):
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
    return loc.get_by_role("main").last


def loc_map(loc: Locator) -> Locator:
    return loc.get_by_role("link", name="Map")


def loc_people(loc: Locator) -> Locator:
    return loc_info(loc).get_by_role("link", name="Photo of ")


class MediaItemMetadata(BaseModel):
    item: str = ""
    people: list[str] = Field(default_factory=list)
    albums: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)
    position: str = ""


class Album(BaseModel):
    title: str = ""
    item: str = ""
    media_items_metadata: list[MediaItemMetadata] = Field(default_factory=list)


if __name__ == "__main__":
    run(main())
