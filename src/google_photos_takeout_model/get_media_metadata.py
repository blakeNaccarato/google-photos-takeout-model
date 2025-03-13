from __future__ import annotations

from asyncio import Lock, Task, TaskGroup, run, sleep
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from itertools import cycle
from json import loads
from pathlib import Path
from re import compile  # noqa: A004
from sys import argv
from typing import Any, Literal, TypeVar

from playwright.async_api import Locator, TimeoutError  # noqa: A004
from pydantic import BaseModel, Field
from stamina import retry
from stamina.instrumentation import set_on_retry_hooks
from tqdm.asyncio import tqdm as atqdm
from tqdm.std import tqdm

from google_photos_takeout_model import WAIT, dumps
from google_photos_takeout_model.pw import (
    INTERACT_TIMEOUT,
    STORAGE_STATE,
    locator,
    logged_in,
)

URLS = argv[1:]
OVERWRITE = True

set_on_retry_hooks([])


def quick_retry(*on: type[Exception]):
    return retry(
        on=on,
        timeout=2.00,
        wait_initial=0.01,
        wait_max=0.50,
        wait_jitter=0.01,
        wait_exp_base=1.70,
    )


def slow_retry(*on: type[Exception]):
    return retry(on=on, attempts=100, timeout=450, wait_max=50)


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


async def main(urls: list[str] = URLS, overwrite: bool = OVERWRITE):
    await login_and_reveal_info()
    async with TaskGroup() as tg:
        for url in urls:
            tg.create_task(process_album(url, overwrite))


async def login_and_reveal_info():
    async with logged_in() as loc:
        await reveal_info(loc)
        await loc.page.context.storage_state(path=STORAGE_STATE)


async def reveal_info(loc):
    await click_first_photo(loc)
    try:
        await loc_info(loc).is_visible(timeout=INTERACT_TIMEOUT)
    except TimeoutError:
        await loc_main(loc).press("i")


async def process_album(url: str, overwrite: bool):
    # TODO: Fix
    async with locator() as loc, album(loc, url) as alb:
        meta = alb.media_items_metadata
        items = len(meta)
        last_item_done = (
            -1
            if overwrite
            else next((i for i, m in enumerate(meta) if not m.item), items)
        )
        if last_item_done < 0:
            async with expect_navigation(loc):
                await click_first_photo(loc)
            meta[0] = await update_media_item_metadata(loc)
            last_item_done = 0
        else:
            await slow_retry(TimeoutError)(loc.page.goto)(meta[last_item_done].item)
        for item in tqdm(range(last_item_done + 1, items)):
            async with expect_navigation(loc):
                await loc_main(loc).press("ArrowRight")
            meta[item] = await update_media_item_metadata(loc)


@quick_retry(RuntimeError, TimeoutError)
async def click_first_photo(loc):
    await loc_first_photo(loc).click(timeout=INTERACT_TIMEOUT)


@asynccontextmanager
async def albums(
    locs: cycle[tuple[Locator, Lock]], progress: atqdm, urls: list[str]
) -> AsyncGenerator[list[Album]]:
    progress.total += len(urls)
    tasks: list[Task[tuple[Album, Path]]] = []
    async with TaskGroup() as tg:
        tasks.extend(
            tg.create_task(get_album(loc, lock, url))
            for url, (loc, lock) in zip(urls, locs, strict=False)
        )
        add_progress_callbacks(progress, tasks)
    progress.total -= len(urls)
    albums = [task.result() for task in tasks]
    try:
        yield [album for album, _ in albums]
    finally:
        for album, path in albums:
            write_album(path, album)


def add_progress_callbacks(progress: atqdm, tasks: list[Task[Any]]):
    update_progress = get_progress_updater(progress)
    for task in tasks:
        task.add_done_callback(update_progress)


def get_progress_updater(progress: atqdm) -> Callable[[Task[Any]], None]:
    def update_progress(_task: Task[Any]):
        progress.update()

    return update_progress


@asynccontextmanager
async def album(loc: Locator, url: str) -> AsyncGenerator[Album]:
    alb, path = await get_album(loc, Lock(), url)
    try:
        yield alb
    finally:
        write_album(path, alb)


async def get_album(loc: Locator, lock: Lock, url: str) -> tuple[Album, Path]:
    await slow_retry(TimeoutError)(loc.page.goto)(url)
    title = (await loc.page.title()).removesuffix(" - Google Photos")
    path = Path(f"{title}.json")
    alb = (
        Album(**loads(path.read_text(encoding="utf-8")))
        if path.exists()
        else Album(title=title, item=url)
    )
    async with lock:
        items = await get_item_count(loc)
    if not len(alb.media_items_metadata):
        alb.media_items_metadata.extend(MediaItemMetadata() for _ in range(items))
    return (alb, path)


@contextmanager
def file_album(path: Path) -> Generator[Album]:
    alb = Album(**loads(path.read_text(encoding="utf-8")))
    try:
        yield alb
    finally:
        write_album(path, alb)


def write_album(path: Path, alb: Album):
    path.write_text(
        encoding="utf-8",
        data=f"{dumps(alb.model_dump(), indent=2, ensure_ascii=False)}\n",
    )


@asynccontextmanager
async def expect_navigation(loc: Locator):
    async with loc.page.expect_navigation():
        yield


@slow_retry(RuntimeError, TimeoutError)
async def update_media_item_metadata(loc: Locator, item: MediaItemMetadata):
    # TODO: Handle 404
    if not (albums := await loc_albums_containing_item(loc).all_inner_texts()):
        raise RuntimeError("Albums element not loaded.")
    position = (
        (await map.locator("[position]").first.get_attribute("position") or "")
        if await (map := loc_map(loc)).count()  # noqa: A001
        else ""
    )
    details = await loc_details(loc).all_inner_texts()
    if position and not details[-1]:
        raise RuntimeError("Location element not loaded.")
    try:
        people = await get_people(loc)
    except RuntimeError:
        people = []
    item.item = loc.page.url
    item.people = people
    item.albums = albums
    item.details = details
    item.position = position


@quick_retry(RuntimeError, TimeoutError)
async def get_people(loc):
    people = await loc_people(loc).all_inner_texts()
    if not people:
        raise RuntimeError("People element not loaded or people not found.")
    return people


async def get_image_preview_source(loc: Locator):
    return await loc_image_preview_source(loc).get_attribute("src")


async def get_item_count(loc: Locator) -> int:
    return (
        int(desc.split()[0])
        if (desc := await loc_media_item_count(loc).get_attribute("content"))
        else 0
    )


async def get_media_item_source(loc: Locator, details: list[str]) -> str:
    if not await loc_photo(loc).is_visible() and "(0 B)" in "".join(details):
        return ""
    async with loc.page.expect_download() as downloader:
        await loc.press("Shift+D")
    download = await downloader.value
    await download.cancel()
    return download.url


def loc_albums_containing_item(loc: Locator) -> Locator:
    return loc_info(loc).get_by_role("link", name=compile(r"\d+\sitems"))


def loc_album_media_items(loc: Locator) -> Locator:
    return loc_main(loc).get_by_role("link", name=compile(r"^(?!Back|Goog|Play).*$"))


def loc_details(loc: Locator):
    return loc_info(loc).locator("div").filter(has=loc.page.locator("> dt > svg"))


def loc_first_photo(loc):
    return loc_main(loc).get_by_role("link", name="Photo - ").first


def loc_image_preview_source(loc: Locator):
    return loc_photo(loc).locator("[src]")


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


def loc_photo(loc):
    return loc_main(loc).filter(has=loc.page.get_by_role("img", name="Photo - ")).last


T = TypeVar("T")
type Check[T] = Callable[[Locator], Coroutine[None, None, T]]
type RetryCheck[T] = Callable[[Locator, Check[T], bool], Coroutine[None, None, T]]
type Errors = type[Exception] | tuple[type[Exception], ...]


def on_retry[T](errors: Errors, f: RetryCheck[T]) -> Callable[[Check[T]], Check[T]]:
    def decorator(check: Check[T]) -> Check[T]:
        @wraps(check)
        async def wrapper(loc: Locator):
            try:
                return await check(loc)
            except errors:
                return await retry(on=errors)(f)(loc, check, False)

        return wrapper

    return decorator


async def retry_reload[T](loc: Locator, check: Check[T], first_try: bool = True) -> T:
    if first_try:
        return await check(loc)
    await loc.page.reload()
    async with wait("before"):
        return await check(loc)


async def retry_logged_in[T](
    loc: Locator, check: Check[T], first_try: bool = True
) -> T:
    if first_try:
        return await check(loc)
    async with logged_in(), wait("before"):
        result = await check(loc)
    await loc.page.context.storage_state(path=STORAGE_STATE)
    return result


@asynccontextmanager
async def wait(kind: Literal["before", "after"], duration: float = WAIT):
    if kind == "before":
        await sleep(duration)
    yield
    if kind == "after":
        await sleep(duration)


if __name__ == "__main__":
    run(main())
