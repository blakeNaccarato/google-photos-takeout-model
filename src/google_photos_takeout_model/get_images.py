from __future__ import annotations

from asyncio import run
from re import compile

from playwright.async_api import Locator

from google_photos_takeout_model import (
    GPHOTOS_ALBUM,
    logged_in,
)


async def main():
    async with logged_in() as (pg, _):
        await pg.goto(GPHOTOS_ALBUM)
        items = pg.get_by_role("link", name=compile(r"^(?!Back to albums).*$"))
        back_to_album_view = pg.get_by_role("link", name="Back to album view")
        await items.first.click()
        await pg.get_by_label("Open info").click()
        await back_to_album_view.click()
        n = -1
        while (n := n + 1) < await items.count():
            item = items.nth(n)
            await item.click()
            elements = pg.get_by_role("main").locator("c-wiz")
            _url = await get_css_attr(elements.nth(2), "src")
            _info = await elements.nth(3).aria_snapshot()
            map = pg.get_by_role("link", name="Map")
            _position = await get_css_attr(map, "position")
            await pg.pause()
            await back_to_album_view.click()


async def get_css_attr(locator: Locator, attr: str) -> str:
    await locator.scroll_into_view_if_needed()
    return await locator.locator(f"[{attr}]").first.get_attribute(attr) or ""


if __name__ == "__main__":
    run(main())
