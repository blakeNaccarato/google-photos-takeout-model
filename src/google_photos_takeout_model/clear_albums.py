from asyncio import run
from sys import argv

from google_photos_takeout_model.get_media_metadata import (
    MediaItemMetadata,
    login_and_reveal_info,
)
from google_photos_takeout_model.get_media_metadata2 import album
from google_photos_takeout_model.pw import context, locator2

ALBUM_URLS = argv[1:]


async def main(urls: list[str] = ALBUM_URLS):
    await login_and_reveal_info()
    async with context() as ctx, locator2(ctx) as loc:
        for url in urls:
            async with album(loc, url) as alb:
                for i, item in enumerate(alb.media_items_metadata):
                    alb.media_items_metadata[i] = MediaItemMetadata(item=item.item)


if __name__ == "__main__":
    run(main())
