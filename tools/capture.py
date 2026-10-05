"""Capture app pages with Playwright; adapted from videoeditinggod/v2/shoot.py."""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urljoin

async def capture(a):
    from playwright.async_api import async_playwright
    pages = json.loads(a.pages.read_text()) if a.pages else [{'name':'overview','path':'/'}]
    a.output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={'width':1920,'height':1080},device_scale_factor=1,
                                      **({'storage_state':str(a.storage_state)} if a.storage_state else {}))
        page = await ctx.new_page()
        for item in pages:
            name = item['name']
            if not name.replace('-','').replace('_','').isalnum():
                raise ValueError('Capture names must be letters, digits, underscores or hyphens.')
            await page.goto(urljoin(a.url,item['path']),wait_until='domcontentloaded')
            if item.get('selector'):
                await page.locator(item['selector']).wait_for()
            await page.screenshot(path=str(a.output/f'{name}.png'),full_page=False)
            print(a.output/f'{name}.png')
        await browser.close()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('url')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pages',type=Path)
    p.add_argument('--storage-state',type=Path,help='Local Playwright login state; keep outside the repo')
    asyncio.run(capture(p.parse_args()))

if __name__ == '__main__':
    main()
