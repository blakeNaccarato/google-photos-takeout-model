from __future__ import annotations

from asyncio import run
from os import environ
from sys import argv

from playwright.async_api import Locator
from tqdm import tqdm

from google_photos_takeout_model import (
    Albums,
    Kinds,
    get_albums,
    logged_in,
    many_photos_selected,
    select_all_photos,
    update_album_list,
)
from google_photos_takeout_model.pw import GPHOTOS_BASE_URL, WAIT


async def main():
    albs = get_albums()
    async with logged_in() as loc:
        for title, url in tqdm(albs["in"].contents.items()):
            await loc.page.goto(url)
            await copy_album(title, albs, loc)


async def copy_album(title: str, albs: dict[Kinds, Albums], loc: Locator):
    gphotos_shared_person = (
        environ.get("GPHOTOS_SHARED_PERSON") or argv[1] if len(argv) > 1 else None
    )
    shared = (
        await loc.page.get_by_role("button", name=gphotos_shared_person).count()
        if gphotos_shared_person
        else False
    )
    unlv_url = loc.page.url
    await select_all_photos(loc)
    if await many_photos_selected(loc):
        return update_album_list(albs["large"], title, loc.page.url)
    # ? Add all images to a new album
    await loc.page.get_by_label("Add to album", exact=True).click()
    await loc.page.get_by_role("menu").get_by_text("Album", exact=True).click()
    await loc.page.wait_for_timeout(WAIT)
    await loc.page.get_by_role("option", name="New album").click()
    # ? Wait for the album to be created
    await loc.page.wait_for_url(f"{GPHOTOS_BASE_URL}/album/*", timeout=60_000)
    # ? Give the new album the same title as the shared album
    album_title = loc.page.get_by_placeholder("Add a title")
    await album_title.click()
    await album_title.fill(title)
    await loc.page.get_by_label("Done").click()
    # ? Update album list
    update_album_list(albs["copied"], title, loc.page.url)
    # ? Record albums that were shared
    if shared:
        update_album_list(albs["shared"], title, unlv_url)
        update_album_list(albs["were-shared"], title, loc.page.url)


if __name__ == "__main__":
    run(main())
