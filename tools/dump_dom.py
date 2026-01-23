"""
Utility script to dump the fully rendered DOM of a green.car model page.

This is useful for:
- Debugging Next.js / client-side rendered pages
- Inspecting accordions and tables without relying on DevTools
- Making the scraper resilient to layout changes
"""

from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://www.green.car/audi/e-tron-gt/saloon-electric"
OUTPUT_FILE = Path("rendered.html")


def dump_dom(url: str, output: Path):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            )
        )
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(2000)

        html = page.content()
        output.write_text(html, encoding="utf-8")

        browser.close()

    print(f"Rendered DOM saved to: {output.resolve()}")


if __name__ == "__main__":
    dump_dom(URL, OUTPUT_FILE)
