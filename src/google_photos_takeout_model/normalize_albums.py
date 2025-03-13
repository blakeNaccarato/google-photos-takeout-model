from sys import argv

from google_photos_takeout_model.get_media_metadata import login_and_reveal_info
from google_photos_takeout_model.get_media_metadata2 import album
from google_photos_takeout_model.pw import context, locator2

ALBUM_URLS = argv[1:]


async def main(urls: list[str] = ALBUM_URLS):
    await login_and_reveal_info()
    async with context() as ctx, locator2(ctx) as loc:
        for url in urls:
            async with album(loc, url):
                pass
