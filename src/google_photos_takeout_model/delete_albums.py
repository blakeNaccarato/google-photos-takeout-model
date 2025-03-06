from __future__ import annotations

from asyncio import run

from playwright.async_api import Page
from tqdm import tqdm

from google_photos_takeout_model import (
    WAIT,
    Albums,
    Kinds,
    get_albums,
    loc_more_options,
    logged_in,
    many_photos_selected,
    more_options,
    select_all_photos,
    update_album_list,
)
from google_photos_takeout_model.pw import TIMEOUT

# TODO: Implement as finite state machine, e.g. awaiting empty album depends on state.


async def main():
    albs = get_albums()
    async with logged_in() as pg:
        for title, url in tqdm(albs["in"].contents.items()):
            await pg.goto(url)
            await leave_or_delete_album(title, albs, pg)


async def leave_or_delete_album(title: str, albs: dict[Kinds, Albums], pg: Page):
    unlv_url = pg.url
    if not await pg.get_by_role("checkbox").count():
        await delete_album(pg)
        return update_album_list(albs["deleted"], title, unlv_url)
    await select_all_photos(pg)
    if await many_photos_selected(pg):
        update_album_list(albs["large"], title, pg.url)
    # ? Move all images to trash
    await more_options(pg)
    if await pg.get_by_text("Move to trash").count():
        await move_to_trash(pg)
        return update_album_list(albs["deleted"], title, unlv_url)
    await pg.get_by_label("Clear selection").click()
    # ? Leave album if it's not ours
    await more_options(pg)
    leave_album = pg.get_by_label("Leave album")
    if await leave_album.count():
        await leave_album.click()
        await pg.get_by_role("button", name="Leave Album").click()
        return update_album_list(albs["left"], title, unlv_url)
    else:
        await move_to_trash(pg)
    update_album_list(albs["deleted"], title, unlv_url)


async def move_to_trash(pg: Page):
    move_to_trash = pg.get_by_text("Move to trash")
    if await move_to_trash.count():
        await move_to_trash.click()
        await pg.get_by_role("button", name="Move to trash").click()
        while await pg.get_by_text("Moving to trash").count():
            await pg.wait_for_timeout(WAIT)
    else:
        await pg.get_by_label("Delete album").click()
        await pg.get_by_role("button", name="Delete").click()
        return
    waited = 0
    while (waited < TIMEOUT) and (
        await loc_more_options(pg).count() or not await album_empty_after_deleting(pg)
    ):
        waited += WAIT
        await pg.wait_for_timeout(WAIT)
    if await album_empty_after_deleting(pg):
        return await pg.get_by_role("button", name="Delete").click()
    await delete_album(pg)


async def album_empty_after_deleting(pg: Page):
    return await pg.get_by_text("Delete empty album?").count()


async def delete_album(pg: Page):
    await more_options(pg)
    await pg.get_by_label("Delete album").click()
    await pg.get_by_role("button", name="Delete").click()


if __name__ == "__main__":
    run(main())
