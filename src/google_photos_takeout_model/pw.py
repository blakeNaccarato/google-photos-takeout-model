from contextlib import asynccontextmanager
from os import environ
from pathlib import Path
from threading import Thread

import pyautogui
from playwright.async_api import BrowserContext, Page, PlaywrightContextManager
from pyautogui import hotkey

pyautogui.PAUSE = 0.2
GPHOTOS_BASE_URL = "https://photos.google.com"
STORAGE_STATE = Path("storage-state.json")
LARGE_ALBUM_COUNT = 400
SLOW_MO_WAIT = 200
WAIT = 1_000
LONG_WAIT = 5_000
TIMEOUT = 15_000


@asynccontextmanager
async def browser():
    environ["PWDEBUG"] = "1"
    async with PlaywrightContextManager() as pw:
        browser = await pw.chromium.launch(
            args=["--disable-blink-features=AutomationControlled"],
            channel="chrome",
            headless=False,
            slow_mo=SLOW_MO_WAIT,
        )
        yield browser
        browser.close()


@asynccontextmanager
async def context():
    if not STORAGE_STATE.exists():
        STORAGE_STATE.write_text(encoding="utf-8", data="{}")
    async with browser() as b:
        ctx = await b.new_context(storage_state=STORAGE_STATE, no_viewport=True)
        yield ctx
        await ctx.close()


@asynccontextmanager
async def page():
    async with context() as ctx:
        pg = await ctx.new_page()
        yield pg
        await pg.close()


async def log_in_if_not(pg: Page, ctx: BrowserContext):
    logged_in = not await pg.get_by_label("Sign in").count()
    if not logged_in:
        await log_in(pg)


async def log_in(pg: Page):
    Thread(target=move_windows, daemon=True).start()
    await pg.goto(f"{GPHOTOS_BASE_URL}/login")
    if any(
        [
            await pg.get_by_role("heading", name=name, exact=True).count()
            for name in ["Sign in", "Choose an account"]
        ]
    ):
        await pg.wait_for_url("https://photos.google.com/", timeout=90_000)
    await pg.context.storage_state(path=STORAGE_STATE)
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
