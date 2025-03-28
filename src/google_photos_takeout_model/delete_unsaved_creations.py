from __future__ import annotations

from asyncio import run

from google_photos_takeout_model.pw import (
    GPHOTOS_BASE_URL,
    logged_in,
)


async def main():
    async with logged_in() as loc:
        await loc.page.goto(f"{GPHOTOS_BASE_URL}/unsaved")
        options = loc.page.get_by_role("button", name="More options", exact=True)
        delete = loc.page.get_by_role("menuitem", name="Delete permanently", exact=True)
        n = -1
        while (n := n + 1) < 1000 and await options.count():
            await options.nth(n).hover(force=True)
            await options.nth(n).click(force=True)
            if await delete.is_visible():
                await delete.click(force=True)


if __name__ == "__main__":
    run(main())
