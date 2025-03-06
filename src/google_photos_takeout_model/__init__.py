"""Model for Google Takeout data for Google Photos."""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from json import dumps, loads
from pathlib import Path
from typing import Literal, Self, TypeAlias, get_args

from playwright.async_api import Locator, Page

from google_photos_takeout_model.pw import (
    LARGE_ALBUM_COUNT,
    LONG_WAIT,
    WAIT,
    log_in,
    page,
)

Kinds: TypeAlias = Literal[
    "copied",
    "deleted",
    "in",
    "large",
    "left",
    "shared",
    "were-shared",
]
kinds = get_args(Kinds)


@dataclass
class Albums:
    path: Path
    contents: dict[str, str]

    @classmethod
    def from_path(cls, path: Path) -> Self:
        if not path.exists():
            path.write_text(encoding="utf-8", data="{}")
        return cls(path, loads(path.read_text(encoding="utf-8")))


async def select_all_photos(pg: Page):
    # ? Select first checkbox
    await pg.get_by_role("checkbox").first.click()
    # ? Move to page bottom to show last checkbox. Do twice since it's flaky
    await pg.keyboard.press("End")
    await pg.wait_for_timeout(WAIT)
    await pg.keyboard.press("Home")
    await pg.wait_for_timeout(WAIT)
    await pg.keyboard.press("End")
    await pg.wait_for_timeout(LONG_WAIT)
    # ? Shift+select last checkbox to select all images
    if not await (last_box := pg.get_by_role("checkbox").last).is_checked():
        await pg.keyboard.down("Shift")
        await last_box.click()
        await pg.keyboard.up("Shift")
    await pg.wait_for_timeout(WAIT)


async def many_photos_selected(pg: Page) -> bool:
    return bool(selected := await pg.get_by_text("selected").text_content()) and (
        int(selected.split()[0]) > LARGE_ALBUM_COUNT
    )


def update_album_list(albums: Albums, title: str, url: str):
    albums.contents[title] = url
    albums.path.write_text(
        encoding="utf-8",
        data=f"{dumps(albums.contents, indent=2, ensure_ascii=False)}\n",
    )


def get_albums() -> dict[Kinds, Albums]:
    albs: dict[Kinds, Albums] = {}
    for kind in kinds:
        albs[kind] = Albums.from_path(Path(f"albums-{kind}.json"))
    return albs


@asynccontextmanager
async def logged_in():
    async with page() as pg:
        await log_in(pg)
        yield pg


async def more_options(loc: Page | Locator):
    if isinstance(loc, Page):
        pg = loc
        loc = pg.locator("*")
    else:
        pg = loc.page
    while not await loc_more_options(loc).count():
        await pg.wait_for_timeout(WAIT)
    await loc_more_options(loc).click()
    await pg.wait_for_timeout(WAIT)


def loc_more_options(loc: Page | Locator) -> Locator:
    return loc.get_by_role("button", name="More options")
