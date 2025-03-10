import asyncio

from google_photos_takeout_model.pw import locator


async def main():
    async with locator() as loc:
        await loc.page.goto("https://bot-detector.rebrowser.net")
        await loc.page.pause()


if __name__ == "__main__":
    asyncio.run(main())
