from contextlib import asynccontextmanager
from os import environ
from pathlib import Path

from playwright.async_api import BrowserContext, Page, PlaywrightContextManager

GPHOTOS_BASE_URL = "https://photos.google.com"
STORAGE_STATE = Path("storage-state.json")
LARGE_ALBUM_COUNT = 400
SLOW_MO_WAIT = 500
WAIT = 2 * SLOW_MO_WAIT
LONG_WAIT = 5 * SLOW_MO_WAIT
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
        teardown_page(pg)


@asynccontextmanager
async def page_and_context():
    async with context() as ctx:
        pg = await ctx.new_page()
        yield pg, ctx
        teardown_page(pg)


async def teardown_page(pg: Page):
    await pg.close()


async def log_in_if_not(pg: Page, ctx: BrowserContext):
    logged_in = not await pg.get_by_label("Sign in").count()
    if not logged_in:
        await log_in(pg, ctx)


async def log_in(pg: Page, ctx: BrowserContext):
    await pg.goto(f"{GPHOTOS_BASE_URL}/login")
    await pg.pause()
    await ctx.storage_state(path=STORAGE_STATE)
