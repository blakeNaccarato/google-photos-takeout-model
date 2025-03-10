from contextlib import asynccontextmanager
from os import environ
from pathlib import Path

import pyautogui
from playwright.async_api import Locator, PlaywrightContextManager, ViewportSize

EMAIL = environ["GPHOTOS_EMAIL"]
PASSWORD = environ["GPHOTOS_PASSWORD"]

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
NAV_TIMEOUT = 5_000
LOGIN_TIMEOUT = 30_000


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
async def context(headless: bool = True, login: bool = False):
    if not STORAGE_STATE.exists():
        STORAGE_STATE.write_text(encoding="utf-8", data="{}")
    async with browser(headless=False if login else headless) as b:
        ctx = await b.new_context(
            reduced_motion="reduce",
            storage_state=STORAGE_STATE,
            viewport=None if login else ViewportSize(width=1920, height=5000),
        )
        yield ctx
        await ctx.close()


@asynccontextmanager
async def locator(headless: bool = True, login: bool = False):
    async with context(headless, login) as ctx:
        pg = await ctx.new_page()
        loc = pg.locator("*")
        yield loc
        await loc.page.close()


@asynccontextmanager
async def logged_in():
    async with locator(login=True) as loc:
        await log_in(loc)
        yield loc


async def log_in(loc: Locator):
    async with loc.page.expect_navigation(
        url=f"{GPHOTOS_BASE_URL}/", timeout=LOGIN_TIMEOUT
    ):
        await loc.page.goto(f"{GPHOTOS_BASE_URL}/login")
        if await loc_exact_heading(loc, "Sign in").count():
            await loc.get_by_label("Email or phone", exact=True).fill(EMAIL)
            await loc_next(loc).click()
            await loc_password(loc).fill(PASSWORD)
            await loc_next(loc).click()
            if await loc.get_by_text("2-Step Verification", exact=True).count():
                pass
        elif await loc_exact_heading(loc, "Choose an account").count():
            await loc.page.pause()  # TODO: Fix
            await loc.get_by_role("link", name="Blake Naccarato").click()  # TODO: Fix
            await loc_password(loc).fill(PASSWORD)
            await loc_next(loc).click()
    await loc.page.context.storage_state(path=STORAGE_STATE)


def loc_password(loc: Locator) -> Locator:
    return loc.get_by_label("Enter your password", exact=True)


def loc_next(loc: Locator) -> Locator:
    return loc.get_by_role("button", name="Next", exact=True)


def loc_exact_heading(loc: Locator, name: str) -> Locator:
    return loc.page.get_by_role("heading", name=name, exact=True)
