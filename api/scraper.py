import re
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import orjson
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .settings import REQUIRED_SECTIONS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _get_rendered_html(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1500)
        html = page.content()
        browser.close()
    return html


def _parse_make_and_range(url: str, soup: BeautifulSoup) -> Tuple[str, str]:
    parts = [p for p in url.split("/") if p]
    manufacturer = parts[-3].title()
    h1 = soup.find("h1")
    vehicle_range = _clean(h1.get_text()) if h1 else "Unknown"
    return manufacturer, vehicle_range


def _icon_to_bool(td) -> str:
    icon = td.find(attrs={"title": re.compile("(check|cross)-circled", re.I)})
    if not icon:
        return ""
    return "true" if "check" in icon["title"].lower() else "false"


def extract_features(soup: BeautifulSoup) -> Dict[str, List[Dict[str, str]]]:
    result = {s: [] for s in REQUIRED_SECTIONS}

    accordions = soup.find_all("div", class_=re.compile("AccordionItemContainer", re.I))
    for acc in accordions:
        title_span = acc.find("span", class_=re.compile("AccordionItemText", re.I))
        if not title_span:
            continue

        section = _clean(title_span.get_text())
        if section not in result:
            continue

        body = acc.find("div", class_=re.compile("AccordionItemBody", re.I))
        if not body:
            continue

        for tr in body.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue

            name = _clean(tds[0].get_text())
            value = _icon_to_bool(tds[1]) if len(tds) > 1 else ""

            result[section].append(
                {"feature_name": name, "feature_value": value}
            )

    return result


def extract_summary(soup: BeautifulSoup) -> List[Dict[str, str]]:
    rows = []
    node = soup.find(lambda t: t.get_text(strip=True).lower() == "summary")
    if not node:
        return rows

    container = node
    for _ in range(5):
        if container.parent:
            container = container.parent

    for line in container.get_text("\n").splitlines():
        line = _clean(line)
        if ":" in line:
            k, v = line.split(":", 1)
            rows.append({"summary_key": _clean(k), "summary_value": _clean(v)})

    return rows


def scrape_page(url: str):
    html = _get_rendered_html(url)
    soup = BeautifulSoup(html, "lxml")

    scraped_at = _utc_now()
    manufacturer, vehicle_range = _parse_make_and_range(url, soup)

    summary = extract_summary(soup)
    for r in summary:
        r.update({
            "scraped_at": scraped_at,
            "page_url": url,
            "manufacturer": manufacturer,
            "vehicle_range": vehicle_range,
        })

    features = []
    by_section = extract_features(soup)
    for section, items in by_section.items():
        for it in items:
            features.append({
                "scraped_at": scraped_at,
                "page_url": url,
                "manufacturer": manufacturer,
                "vehicle_range": vehicle_range,
                "section": section,
                **it,
            })

    return summary, features


def write_jsonl(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as f:
        for r in rows:
            f.write(orjson.dumps(r))
            f.write(b"\n")
