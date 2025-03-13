from asyncio import Lock, Task, TaskGroup, run
from contextlib import asynccontextmanager
from itertools import cycle
from sys import argv
from typing import Any

from playwright.async_api import Locator, TimeoutError  # noqa: A004
from tqdm.asyncio import tqdm

from google_photos_takeout_model.get_media_metadata import (
    MediaItemMetadata,
    add_progress_callbacks,
    albums,
    login_and_reveal_info,
    slow_retry,
    update_media_item_metadata,
)
from google_photos_takeout_model.pw import context

type Batch = tuple[int, tuple[MediaItemMetadata, ...]]


ALBUM_URLS = argv[1:]
PAGES = 24
OVERWRITE = False


async def main(
    urls: list[str] = ALBUM_URLS, pages: int = PAGES, overwrite: bool = OVERWRITE
):
    async with tasks(urls, pages, overwrite) as (tg, ts, loop, items):
        for idx, ((loc, lock), _item) in loop:
            ts.append(tg.create_task(process_item(loc, lock, items, idx)))


@asynccontextmanager
async def tasks(
    urls: list[str] = ALBUM_URLS, pages: int = PAGES, overwrite: bool = OVERWRITE
):
    progress = tqdm(smoothing=0, total=0)
    await login_and_reveal_info()
    async with context() as ctx, TaskGroup() as tg:
        items: list[MediaItemMetadata] = []
        locators = [((await ctx.new_page()).locator("*"), Lock()) for _ in range(pages)]
        locs = cycle(locators)
        async with albums(locs, progress, urls) as albs:
            for alb in albs:
                meta = alb.media_items_metadata
                if overwrite:
                    items.extend(meta)
                else:
                    items.extend([item for item in meta if not item.details])
            progress.total += len(items)
            loop = enumerate(zip(locs, items, strict=False))
            ts: list[Task[Any]] = []
            async with TaskGroup() as tg:
                yield tg, ts, loop, items
                add_progress_callbacks(progress, ts)
            for loc, _ in locators:
                await loc.page.close()
    progress.close()


async def process_item(
    loc: Locator, lock: Lock, media_items_metadata: list[MediaItemMetadata], idx: int
):
    item = media_items_metadata[idx]
    if not item.item:
        return
    async with lock:
        await slow_retry(TimeoutError)(loc.page.goto)(item.item)
        await update_media_item_metadata(loc, media_items_metadata[idx])


if __name__ == "__main__":
    run(main())
