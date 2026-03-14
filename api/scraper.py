import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import orjson
from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .logging_utils import log_event
from .settings import SourceDefinition, get_settings

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    run_id: str
    source_id: str
    url: str
    summary: List[Dict[str, str]]
    features: List[Dict[str, str]]
    warnings: List[str]
    content_fingerprint: str
    timings_ms: Dict[str, int]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _duration_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _get_rendered_html(url: str) -> str:
    settings = get_settings()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(
                url,
                wait_until="networkidle",
                timeout=settings.runtime.browser_timeout_ms,
            )
            page.wait_for_timeout(settings.runtime.browser_wait_ms)
            return page.content()
        finally:
            browser.close()


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


def extract_features(
    soup: BeautifulSoup, required_sections: List[str]
) -> tuple[Dict[str, List[Dict[str, str]]], List[str]]:
    result: Dict[str, List[Dict[str, str]]] = {
        section: [] for section in required_sections
    }
    warnings: List[str] = []

    accordions = soup.find_all("div", class_=re.compile("AccordionItemContainer", re.I))
    if not accordions:
        warnings.append("feature_sections_not_found")
        return result, warnings

    for acc in accordions:
        title_span = acc.find("span", class_=re.compile("AccordionItemText", re.I))
        if not title_span:
            continue

        section = _clean(title_span.get_text())
        if section not in result:
            continue

        body = acc.find("div", class_=re.compile("AccordionItemBody", re.I))
        if not body:
            warnings.append(f"missing_section_body:{section}")
            continue

        for tr in body.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue

            name = _clean(tds[0].get_text())
            value = _icon_to_bool(tds[1]) if len(tds) > 1 else ""

            result[section].append({"feature_name": name, "feature_value": value})

    missing_sections = [section for section, items in result.items() if not items]
    warnings.extend([f"missing_section:{section}" for section in missing_sections])
    return result, warnings


def extract_summary(soup: BeautifulSoup) -> tuple[List[Dict[str, str]], List[str]]:
    rows: List[Dict[str, str]] = []
    node = soup.find(lambda t: t.get_text(strip=True).lower() == "summary")
    if not node:
        return rows, ["summary_section_not_found"]

    container = node
    for _ in range(5):
        if container.parent:
            container = container.parent

    for line in container.get_text("\n").splitlines():
        line = _clean(line)
        if ":" in line:
            k, v = line.split(":", 1)
            rows.append({"summary_key": _clean(k), "summary_value": _clean(v)})

    if not rows:
        return rows, ["summary_rows_empty"]
    return rows, []


def _stable_row(row: Dict[str, str]) -> Dict[str, str]:
    return {k: v for k, v in row.items() if k != "scraped_at"}


def build_content_fingerprint(
    summary: List[Dict[str, str]], features: List[Dict[str, str]]
) -> str:
    payload = {
        "summary": sorted(
            (_stable_row(row) for row in summary),
            key=lambda row: (row.get("summary_key", ""), row.get("summary_value", "")),
        ),
        "features": sorted(
            (_stable_row(row) for row in features),
            key=lambda row: (
                row.get("section", ""),
                row.get("feature_name", ""),
                row.get("feature_value", ""),
            ),
        ),
    }
    return hashlib.sha256(
        orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()


def scrape_page(url: str, source: SourceDefinition, run_id: str) -> ScrapeResult:
    warnings: List[str] = []
    timings_ms: Dict[str, int] = {}

    render_start = time.perf_counter()
    html = _get_rendered_html(url)
    timings_ms["render"] = _duration_ms(render_start)

    parse_start = time.perf_counter()
    soup = BeautifulSoup(html, "lxml")
    manufacturer, vehicle_range = _parse_make_and_range(url, soup)
    timings_ms["parse_metadata"] = _duration_ms(parse_start)

    summary_start = time.perf_counter()
    summary, summary_warnings = extract_summary(soup)
    timings_ms["parse_summary"] = _duration_ms(summary_start)
    warnings.extend(summary_warnings)

    features_start = time.perf_counter()
    by_section, feature_warnings = extract_features(soup, source.required_sections)
    timings_ms["parse_features"] = _duration_ms(features_start)
    warnings.extend(feature_warnings)

    scraped_at = _utc_now()
    for row in summary:
        row.update(
            {
                "scraped_at": scraped_at,
                "page_url": url,
                "manufacturer": manufacturer,
                "vehicle_range": vehicle_range,
            }
        )

    features = []
    for section, items in by_section.items():
        for item in items:
            features.append(
                {
                    "scraped_at": scraped_at,
                    "page_url": url,
                    "manufacturer": manufacturer,
                    "vehicle_range": vehicle_range,
                    "section": section,
                    **item,
                }
            )

    if not summary:
        warnings.append("summary_extract_empty")
    if not features:
        warnings.append("feature_extract_empty")

    content_fingerprint = build_content_fingerprint(summary, features)
    log_event(
        logger,
        logging.INFO,
        "scrape_parsed",
        run_id=run_id,
        source_id=source.source_id,
        url=url,
        warnings=warnings,
        summary_rows=len(summary),
        feature_rows=len(features),
        timings_ms=timings_ms,
        content_fingerprint=content_fingerprint,
    )

    return ScrapeResult(
        run_id=run_id,
        source_id=source.source_id,
        url=url,
        summary=summary,
        features=features,
        warnings=warnings,
        content_fingerprint=content_fingerprint,
        timings_ms=timings_ms,
    )


def write_jsonl(rows, path, *, run_id: str | None = None, source_id: str | None = None):
    start = time.perf_counter()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as f:
        for row in rows:
            f.write(orjson.dumps(row))
            f.write(b"\n")
    log_event(
        logger,
        logging.INFO,
        "jsonl_written",
        run_id=run_id,
        source_id=source_id,
        path=str(path),
        row_count=len(rows),
        duration_ms=_duration_ms(start),
    )


__all__ = [
    "PlaywrightTimeoutError",
    "ScrapeResult",
    "_clean",
    "_icon_to_bool",
    "build_content_fingerprint",
    "extract_features",
    "extract_summary",
    "scrape_page",
    "write_jsonl",
]
