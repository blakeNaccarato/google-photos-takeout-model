from __future__ import annotations

from asyncio import run

from playwright.async_api import Locator
from tqdm import tqdm

from google_photos_takeout_model import (
    WAIT,
    Albums,
    Kinds,
    get_albums,
    loc_more_options,
    many_photos_selected,
    more_options,
    select_all_photos,
    update_album_list,
)
from google_photos_takeout_model.pw import DELETE_ALBUM_TIMEOUT, logged_in

# TODO: Implement as finite state machine, e.g. awaiting empty album depends on state.


async def main():
    albs = get_albums()
    async with logged_in() as loc:
        for title, url in tqdm(albs["in"].contents.items()):
            await loc.page.goto(url)
            await leave_or_delete_album(title, albs, loc)


async def leave_or_delete_album(title: str, albs: dict[Kinds, Albums], loc: Locator):
    unlv_url = loc.page.url
    if not await loc.page.get_by_role("checkbox").count():
        await delete_album(loc)
        return update_album_list(albs["deleted"], title, unlv_url)
    await select_all_photos(loc)
    if await many_photos_selected(loc):
        update_album_list(albs["large"], title, loc.page.url)
    # ? Move all images to trash
    await more_options(loc)
    if await loc.page.get_by_text("Move to trash").count():
        await move_to_trash(loc)
        return update_album_list(albs["deleted"], title, unlv_url)
    await loc.page.get_by_label("Clear selection").click()
    # ? Leave album if it's not ours
    await more_options(loc)
    leave_album = loc.page.get_by_label("Leave album")
    if await leave_album.count():
        await leave_album.click()
        await loc.page.get_by_role("button", name="Leave Album").click()
        return update_album_list(albs["left"], title, unlv_url)
    else:
        await move_to_trash(loc)
    update_album_list(albs["deleted"], title, unlv_url)


async def move_to_trash(loc: Locator):
    move_to_trash = loc.page.get_by_text("Move to trash")
    if await move_to_trash.count():
        await move_to_trash.click()
        await loc.page.get_by_role("button", name="Move to trash").click()
        while await loc.page.get_by_text("Moving to trash").count():
            await loc.page.wait_for_timeout(WAIT)
    else:
        await loc.page.get_by_label("Delete album").click()
        await loc.page.get_by_role("button", name="Delete").click()
        return
    waited = 0
    while (waited < DELETE_ALBUM_TIMEOUT) and (
        await loc_more_options(loc).count() or not await album_empty_after_deleting(loc)
    ):
        waited += WAIT
        await loc.page.wait_for_timeout(WAIT)
    if await album_empty_after_deleting(loc):
        return await loc.page.get_by_role("button", name="Delete").click()
    await delete_album(loc)


async def album_empty_after_deleting(loc: Locator):
    return await loc.page.get_by_text("Delete empty album?").count()


async def delete_album(loc: Locator):
    await more_options(loc)
    await loc.page.get_by_label("Delete album").click()
    await loc.page.get_by_role("button", name="Delete").click()


if __name__ == "__main__":
    run(main())
