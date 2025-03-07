from contextlib import asynccontextmanager
from os import environ
from pathlib import Path
from threading import Thread

import pyautogui
from playwright.async_api import Locator, PlaywrightContextManager
from pyautogui import hotkey

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


@asynccontextmanager
async def browser():
    environ["PWDEBUG"] = "1"
    async with PlaywrightContextManager() as pw:
        browser = await pw.chromium.launch(
            args=["--disable-blink-features=AutomationControlled"],
            channel="chrome",
            headless=False,
            slow_mo=SLOW_MO_WAIT,
            timeout=TIMEOUT,
        )
        yield browser
        await browser.close()


@asynccontextmanager
async def context():
    if not STORAGE_STATE.exists():
        STORAGE_STATE.write_text(encoding="utf-8", data="{}")
    async with browser() as b:
        ctx = await b.new_context(storage_state=STORAGE_STATE, no_viewport=True)
        yield ctx
        await ctx.close()


@asynccontextmanager
async def locator():
    async with context() as ctx:
        pg = await ctx.new_page()
        loc = pg.locator("*")
        yield loc
        await loc.page.close()


async def log_in_if_not(loc: Locator):
    logged_in = not await loc.get_by_label("Sign in").count()
    if not logged_in:
        await log_in(loc)


async def log_in(loc: Locator):
    Thread(target=move_windows, daemon=True).start()
    await loc.page.goto(f"{GPHOTOS_BASE_URL}/login")
    if any(
        [
            await loc.page.get_by_role("heading", name=name, exact=True).count()
            for name in ["Sign in", "Choose an account"]
        ]
    ):
        await loc.page.wait_for_url("https://photos.google.com/", timeout=90_000)
    await loc.page.context.storage_state(path=STORAGE_STATE)
    # ? Zoom browser to smallest scale
    for keys in [["Ctrl", "-"]] * 7:
        hotkey(*keys)


def move_windows():
    alt_tab = ["Alt", "Tab"]
    move_right = [
        ["Win", "Left"],
        ["Win", "Right"],
        ["Win", "Up"],
    ]
    for keys in [
        # ? Move browser to the right
        *move_right,
        # ? Move inspector to the right and unpause it
        alt_tab,
        *move_right,
        ["F8"],
        # ? Focus the browser
        alt_tab,
    ]:
        hotkey(*keys)
