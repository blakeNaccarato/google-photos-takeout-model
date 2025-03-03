from __future__ import annotations

from asyncio import run

from playwright.async_api import Page
from tqdm import tqdm

from google_photos_takeout_model import (
    GPHOTOS_SHARED_PERSON,
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
    async with logged_in() as (pg, _):
        for title, url in tqdm(albs["in"].contents.items()):
            await pg.goto(url)
            await copy_album(title, albs, pg)


async def copy_album(title: str, albs: dict[Kinds, Albums], pg: Page):
    shared = (
        await pg.get_by_role("button", name=GPHOTOS_SHARED_PERSON).count()
        if GPHOTOS_SHARED_PERSON
        else False
    )
    unlv_url = pg.url
    await select_all_photos(pg)
    if await many_photos_selected(pg):
        return update_album_list(albs["large"], title, pg.url)
    # ? Add all images to a new album
    await pg.get_by_label("Add to album", exact=True).click()
    await pg.get_by_role("menu").get_by_text("Album", exact=True).click()
    await pg.wait_for_timeout(WAIT)
    await pg.get_by_role("option", name="New album").click()
    # ? Wait for the album to be created
    await pg.wait_for_url(f"{GPHOTOS_BASE_URL}/album/*", timeout=60_000)
    # ? Give the new album the same title as the shared album
    album_title = pg.get_by_placeholder("Add a title")
    await album_title.click()
    await album_title.fill(title)
    await pg.get_by_label("Done").click()
    # ? Update album list
    update_album_list(albs["copied"], title, pg.url)
    # ? Record albums that were shared
    if shared:
        update_album_list(albs["shared"], title, unlv_url)
        update_album_list(albs["were-shared"], title, pg.url)


if __name__ == "__main__":
    run(main())
