import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app


client = TestClient(app)


def test_scrape_invalid_url():
    """Test that scraping with invalid URL returns 400."""
    response = client.post("/scrape", json={"url": "https://invalid.com"})
    assert response.status_code == 400
    assert "URL not allowed" in response.json()["detail"]


@patch("api.main.scrape_page")
@patch("api.main.write_jsonl")
def test_scrape_valid_url(mock_write_jsonl, mock_scrape_page):
    """Test successful scraping with valid URL."""
    # Mock the scraper return
    mock_scrape_page.return_value = (
        [{"summary_key": "key1", "summary_value": "val1"}],  # summary
        [{"feature_name": "feat1", "feature_value": "true"}]  # features
    )

    response = client.post("/scrape", json={"url": "https://www.green.car/audi/e-tron-gt/saloon-electric"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["extracted_summary_rows"] == 1
    assert data["extracted_features"] == 1
    assert "summary_" in data["summary_file"]
    assert "features_" in data["features_file"]

    # Check that write_jsonl was called twice
    assert mock_write_jsonl.call_count == 2