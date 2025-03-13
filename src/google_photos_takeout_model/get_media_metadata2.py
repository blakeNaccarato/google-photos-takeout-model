from asyncio import TaskGroup, run
from collections.abc import Generator
from itertools import batched, islice
from sys import argv

import more_itertools
from playwright.async_api import BrowserContext, TimeoutError  # noqa: A004
from tqdm import tqdm

from google_photos_takeout_model.get_media_metadata import (
    MediaItemMetadata,
    album,
    get_media_item_metadata,
    login_and_reveal_info,
    slow_retry,
)
from google_photos_takeout_model.pw import context, locator2

type Batch = tuple[int, tuple[MediaItemMetadata, ...]]

# TODO: Do away with batches and instead distribute a lock for each Chrome tab.

ALBUM_URLS = argv[1:]
BATCH_SIZE = 20
OVERWRITE = False


async def main(
    urls: list[str] = ALBUM_URLS,
    batch_size: int = BATCH_SIZE,
    overwrite: bool = OVERWRITE,
):
    await login_and_reveal_info()
    async with context() as ctx, TaskGroup() as tg:
        for url in urls:
            tg.create_task(process_album(ctx, url, batch_size // len(urls), overwrite))


async def process_album(ctx: BrowserContext, url: str, size: int, overwrite: bool):
    async with locator2(ctx) as loc, album(loc, url) as alb:
        meta = alb.media_items_metadata
        for batch_start_idx, batch in batches(meta, size, overwrite):
            for idx, item in (
                (batch_start_idx + item_idx, item)
                for item_idx, item in enumerate(await process_batch(ctx, batch))
            ):
                alb.media_items_metadata[idx] = item


async def process_batch(
    ctx: BrowserContext, batch: tuple[MediaItemMetadata, ...]
) -> list[MediaItemMetadata]:
    async with TaskGroup() as tg:
        tasks = [tg.create_task(process_item(ctx, url=meta.item)) for meta in batch]
    return [task.result() for task in tasks]


async def process_item(ctx: BrowserContext, url: str) -> MediaItemMetadata:
    if not url:
        return MediaItemMetadata()
    async with locator2(ctx) as loc:
        await slow_retry(TimeoutError)(loc.page.goto)(url)
        return await get_media_item_metadata(loc)


def batches(
    meta: list[MediaItemMetadata], size: int, overwrite: bool
) -> Generator[Batch]:
    if not (doable := get_batches_with_urls(meta, size)):
        raise RuntimeError("No items have URLs.")
    finished = 0 if overwrite else get_batches_with_albums(meta, size)
    yield from tqdm(
        islice(
            ((idx * size, item) for idx, item in enumerate(batched(meta, n=size))),
            (first := get_first_batch(meta, size, overwrite)),
            first + (total := doable - finished),
        ),
        total=total,
    )


def get_first_batch(meta: list[MediaItemMetadata], size: int, overwrite: bool) -> int:
    return 0 if overwrite else get_batches_with_albums(meta, size)


def get_batches_with_urls(meta: list[MediaItemMetadata], size: int) -> int:
    return (
        more_itertools.first((i for i, m in enumerate(meta) if not m.item), len(meta))
        // size
    )


def get_batches_with_albums(meta: list[MediaItemMetadata], size: int) -> int:
    return (
        more_itertools.first((i for i, m in enumerate(meta) if not m.albums), len(meta))
        // size
    )


if __name__ == "__main__":
    run(main())
