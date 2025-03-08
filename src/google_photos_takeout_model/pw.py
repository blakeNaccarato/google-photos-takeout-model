from asyncio import TaskGroup
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable, Coroutine, TypeAlias

import pyautogui
from more_itertools import first
from playwright.async_api import Locator, PlaywrightContextManager, ViewportSize

StringProcessor: TypeAlias = Callable[[str, Locator], Coroutine[Any, Any, None]]

pyautogui.PAUSE = 0.2
GPHOTOS_BASE_URL = "https://photos.google.com"
STORAGE_STATE = Path("storage-state.json")
ITEM_SELECTION_THRESHOLD = 491
"""Behavior varies when selections exceed this threshold, resulting in batching."""
SLOW_MO_WAIT = 0
WAIT = 600
LONG_WAIT = 5_000
DELETE_ALBUM_TIMEOUT = 15_000
TIMEOUT = 1_000


async def process_strings(
    f: StringProcessor, strings: list[str], debug: bool = False, headless: bool = False
):
    async with logged_in():
        pass
    if debug:
        return await process_string(f, first(strings))
    async with TaskGroup() as tg:
        for string in strings:
            tg.create_task(process_string(f, string))


async def process_string(f: StringProcessor, string: str):
    async with locator() as loc:
        await f(string, loc)


@asynccontextmanager
async def browser(headless: bool = True):
    async with PlaywrightContextManager() as pw:
        browser = await pw.chromium.launch(
            args=[
                "--disable-blink-features=AutomationControlled",
                "--hide-scrollbars",
                "--mute-audio",
            ],
            channel="chrome",
            headless=headless,
            slow_mo=SLOW_MO_WAIT,
            timeout=TIMEOUT,
        )
        yield browser
        await browser.close()


@asynccontextmanager
async def context(headless: bool = True):
    if not STORAGE_STATE.exists():
        STORAGE_STATE.write_text(encoding="utf-8", data="{}")
    async with browser(headless) as b:
        ctx = await b.new_context(
            storage_state=STORAGE_STATE,
            viewport=ViewportSize(width=1920, height=5000) if headless else None,
        )
        yield ctx
        await ctx.close()


@asynccontextmanager
async def locator(headless: bool = True):
    async with context(headless) as ctx:
        pg = await ctx.new_page()
        loc = pg.locator("*")
        yield loc
        await loc.page.close()


@asynccontextmanager
async def logged_in(headless: bool = False):
    async with locator(headless) as loc:
        await log_in(loc)
        yield loc


async def log_in(loc: Locator):  # sourcery skip: comprehension-to-generator
    await loc.page.goto(f"{GPHOTOS_BASE_URL}/login")
    if any(
        [
            await loc.page.get_by_role("heading", name=name, exact=True).count()
            for name in ["Sign in", "Choose an account"]
        ]
    ):
        await loc.page.wait_for_url("https://photos.google.com/", timeout=90_000)
    await loc.page.context.storage_state(path=STORAGE_STATE)
