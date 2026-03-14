from pathlib import Path

from bs4 import BeautifulSoup

from api.scraper import (
    _clean,
    _icon_to_bool,
    build_content_fingerprint,
    extract_features,
    extract_summary,
    scrape_page,
)
from api.settings import SourceDefinition

FIXTURE_HTML = Path(__file__).parent / "fixtures" / "green_car_vehicle.html"


def load_fixture_html() -> str:
    return FIXTURE_HTML.read_text(encoding="utf-8")


def test_clean():
    assert _clean("  hello   world  ") == "hello world"
    assert _clean("multiple   spaces") == "multiple spaces"
    assert _clean("") == ""
    assert _clean(None) == ""


def test_icon_to_bool():
    soup = BeautifulSoup('<td><span title="check-circled"></span></td>', "html.parser")
    td = soup.find("td")
    assert _icon_to_bool(td) == "true"

    soup = BeautifulSoup('<td><span title="cross-circled"></span></td>', "html.parser")
    td = soup.find("td")
    assert _icon_to_bool(td) == "false"

    soup = BeautifulSoup("<td>No icon</td>", "html.parser")
    td = soup.find("td")
    assert _icon_to_bool(td) == ""


def test_extract_summary_from_fixture():
    soup = BeautifulSoup(load_fixture_html(), "html.parser")
    result, warnings = extract_summary(soup)
    assert warnings == []
    assert result == [
        {"summary_key": "Battery", "summary_value": "93.4 kWh"},
        {"summary_key": "Power", "summary_value": "390 kW"},
    ]


def test_extract_summary_missing_section():
    soup = BeautifulSoup(
        "<html><body><div>No summary here</div></body></html>", "html.parser"
    )
    result, warnings = extract_summary(soup)
    assert result == []
    assert warnings == ["summary_section_not_found"]


def test_extract_features_from_fixture():
    soup = BeautifulSoup(load_fixture_html(), "html.parser")
    required_sections = ["Interior Features", "Entertainment", "Security"]
    result, warnings = extract_features(soup, required_sections)
    assert result["Interior Features"][0]["feature_name"] == "Heated Seats"
    assert result["Interior Features"][0]["feature_value"] == "true"
    assert result["Entertainment"][0]["feature_name"] == "Apple CarPlay"
    assert "missing_section:Security" in warnings


def test_build_content_fingerprint_ignores_scraped_at():
    summary_v1 = [
        {
            "scraped_at": "2024-01-01T00:00:00+00:00",
            "summary_key": "Battery",
            "summary_value": "93.4 kWh",
        }
    ]
    summary_v2 = [
        {
            "scraped_at": "2024-02-01T00:00:00+00:00",
            "summary_key": "Battery",
            "summary_value": "93.4 kWh",
        }
    ]
    features = [
        {
            "scraped_at": "2024-01-01T00:00:00+00:00",
            "section": "Interior Features",
            "feature_name": "Heated Seats",
            "feature_value": "true",
        }
    ]
    assert build_content_fingerprint(summary_v1, features) == build_content_fingerprint(
        summary_v2, features
    )


def test_scrape_page_contract(monkeypatch):
    monkeypatch.setattr(
        "api.scraper._get_rendered_html", lambda url: load_fixture_html()
    )
    source = SourceDefinition(
        source_id="test-source",
        url="https://www.green.car/audi/e-tron-gt/saloon-electric",
        required_sections=["Interior Features", "Entertainment", "Security"],
    )

    result = scrape_page(source.url, source=source, run_id="run-123")

    assert result.run_id == "run-123"
    assert result.source_id == "test-source"
    assert result.summary[0]["manufacturer"] == "Audi"
    assert result.features[0]["vehicle_range"] == "Audi e-tron GT"
    assert "missing_section:Security" in result.warnings
    assert result.content_fingerprint
    assert set(result.timings_ms) == {
        "render",
        "parse_metadata",
        "parse_summary",
        "parse_features",
    }
