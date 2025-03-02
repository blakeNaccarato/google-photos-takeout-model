import asyncio

from google_photos_takeout_model import pw


async def main():
    async with pw.page() as page:
        await page.goto("https://bot-detector.rebrowser.net")
        await page.pause()


if __name__ == "__main__":
    asyncio.run(main())
