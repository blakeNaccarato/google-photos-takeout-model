"""Model for Google Takeout data for Google Photos."""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from json import dumps, loads
from pathlib import Path
from typing import Literal, Self, TypeAlias, get_args

from playwright.async_api import Locator

from google_photos_takeout_model.pw import (
    ITEM_SELECTION_THRESHOLD,
    LONG_WAIT,
    WAIT,
    locator,
    log_in,
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


async def select_all_photos(loc: Locator):
    # ? Select first checkbox
    await loc.page.get_by_role("checkbox").first.click()
    # ? Move to page bottom to show last checkbox. Do twice since it's flaky
    await loc.page.keyboard.press("End")
    await loc.page.wait_for_timeout(WAIT)
    await loc.page.keyboard.press("Home")
    await loc.page.wait_for_timeout(WAIT)
    await loc.page.keyboard.press("End")
    await loc.page.wait_for_timeout(LONG_WAIT)
    # ? Shift+select last checkbox to select all images
    if not await (last_box := loc.page.get_by_role("checkbox").last).is_checked():
        await loc.page.keyboard.down("Shift")
        await last_box.click()
        await loc.page.keyboard.up("Shift")
    await loc.page.wait_for_timeout(WAIT)


async def many_photos_selected(loc: Locator) -> bool:
    return bool(selected := await loc.page.get_by_text("selected").text_content()) and (
        int(selected.split()[0]) > ITEM_SELECTION_THRESHOLD
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
    async with locator() as loc:
        await log_in(loc)
        yield loc


async def more_options(loc: Locator):
    while not await loc_more_options(loc).count():
        await loc.page.wait_for_timeout(WAIT)
    await loc_more_options(loc).click()
    await loc.page.wait_for_timeout(WAIT)


def loc_more_options(loc: Locator) -> Locator:
    return loc.get_by_role("button", name="More options")
