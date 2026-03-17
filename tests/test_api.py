import time
from unittest.mock import patch

from fastapi.testclient import TestClient

import api.main as main_module
from api.main import _docs_config, app, settings
from api.scraper import PlaywrightTimeoutError, ScrapeResult

client = TestClient(app)


def make_result(run_id: str) -> ScrapeResult:
    return ScrapeResult(
        run_id=run_id,
        source_id=settings.active_source.source_id,
        url=settings.active_source.url,
        summary=[{"summary_key": "Battery", "summary_value": "93.4 kWh"}],
        features=[{"feature_name": "Heated Seats", "feature_value": "true"}],
        warnings=["summary_extract_empty"],
        content_fingerprint="abc123",
        timings_ms={"render": 10},
    )


def _reset_guards() -> None:
    main_module._request_window.clear()
    main_module._inflight_sources.clear()


def test_scrape_invalid_url():
    _reset_guards()
    response = client.post("/scrape", json={"url": "https://invalid.com"})
    assert response.status_code == 400
    assert "URL not allowed" in response.json()["detail"]


@patch("api.main.scrape_page")
@patch("api.main.write_jsonl")
def test_scrape_valid_url_returns_run_metadata(mock_write_jsonl, mock_scrape_page):
    _reset_guards()
    mock_scrape_page.return_value = make_result("run-123")
    with patch("api.main._get_latest_scrape_mtime", return_value=None):
        response = client.post("/scrape", json={"url": settings.active_source.url})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["run_id"]
    assert data["extracted_summary_rows"] == 1
    assert data["extracted_features"] == 1
    assert data["warnings"] == ["summary_extract_empty"]
    assert "summary_" in data["summary_file"]
    assert "features_" in data["features_file"]
    assert "/" not in data["summary_file"]
    assert "/" not in data["features_file"]
    assert mock_write_jsonl.call_count == 2


def test_docs_config_disables_docs_in_production(monkeypatch):
    monkeypatch.setattr(settings.runtime, "app_env", "production")
    assert _docs_config() == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }


def test_docs_config_enables_docs_outside_production(monkeypatch):
    monkeypatch.setattr(settings.runtime, "app_env", "development")
    assert _docs_config() == {
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
    }


@patch("api.main.scrape_page")
def test_scrape_timeout_returns_504(mock_scrape_page):
    _reset_guards()
    mock_scrape_page.side_effect = PlaywrightTimeoutError("timed out")
    with patch("api.main._get_latest_scrape_mtime", return_value=None):
        response = client.post("/scrape", json={"url": settings.active_source.url})

    assert response.status_code == 504
    assert response.json()["detail"] == "Scrape timed out"


@patch("api.main.scrape_page")
@patch("api.main.write_jsonl")
def test_scrape_uses_unique_run_id_for_output_files(mock_write_jsonl, mock_scrape_page):
    _reset_guards()
    mock_scrape_page.return_value = make_result("ignored-by-endpoint")

    with patch("api.main._get_latest_scrape_mtime", return_value=None):
        with patch("api.main.new_run_id", side_effect=["run-one", "run-two"]):
            response_one = client.post(
                "/scrape", json={"url": settings.active_source.url}
            )
            response_two = client.post(
                "/scrape", json={"url": settings.active_source.url}
            )

    data_one = response_one.json()
    data_two = response_two.json()
    assert data_one["run_id"] == "run-one"
    assert data_two["run_id"] == "run-two"
    assert data_one["summary_file"] != data_two["summary_file"]
    assert data_one["features_file"] != data_two["features_file"]


def test_scrape_skips_when_data_is_fresh():
    _reset_guards()
    with patch("api.main._get_latest_scrape_mtime", return_value=time.time()):
        response = client.post("/scrape", json={"url": settings.active_source.url})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped"
    assert data["message"] == "skipped_fresh_data"
    assert data["run_id"] == ""


def test_scrape_returns_409_when_source_is_inflight():
    _reset_guards()
    main_module._inflight_sources.add(settings.active_source.source_id)
    try:
        response = client.post("/scrape", json={"url": settings.active_source.url})
    finally:
        main_module._inflight_sources.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "Scrape already running for this source"


def test_scrape_rate_limit_returns_429(monkeypatch):
    _reset_guards()
    monkeypatch.setattr(settings.runtime, "rate_limit_requests", 1)
    monkeypatch.setattr(settings.runtime, "rate_limit_window_seconds", 60)

    with patch("api.main._get_latest_scrape_mtime", return_value=time.time()):
        first = client.post("/scrape", json={"url": settings.active_source.url})
        second = client.post("/scrape", json={"url": settings.active_source.url})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"] == "Rate limit exceeded"
