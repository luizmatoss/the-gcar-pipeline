import json

from api.logging_utils import build_log_payload
from api.settings import load_settings, reset_settings_cache


def test_load_settings_from_catalog_and_env(tmp_path, monkeypatch):
    catalog_path = tmp_path / "sources.json"
    dbt_project_dir = tmp_path / "dbt"
    dbt_project_dir.mkdir()
    temp_raw_dir = tmp_path / "tmp" / "raw"
    temp_gold_dir = tmp_path / "tmp" / "gold"
    catalog_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "source-a",
                        "url": "https://example.com/a",
                        "active": False,
                        "required_sections": ["Interior Features"],
                    },
                    {
                        "source_id": "source-b",
                        "url": "https://example.com/b",
                        "active": True,
                        "required_sections": ["Entertainment"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SOURCE_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("ACTIVE_SOURCE_ID", "source-b")
    monkeypatch.setenv("BROWSER_TIMEOUT_MS", "45000")
    monkeypatch.setenv("BLOB_CONTAINER_NAME", "custom-container")
    monkeypatch.setenv("DBT_PROJECT_DIR", str(dbt_project_dir))
    monkeypatch.setenv("DBT_DATABASE_PATH", str(dbt_project_dir / "custom.duckdb"))
    monkeypatch.setenv("TEMP_RAW_DIR", str(temp_raw_dir))
    monkeypatch.setenv("TEMP_GOLD_DIR", str(temp_gold_dir))

    reset_settings_cache()
    settings = load_settings()

    assert settings.active_source.source_id == "source-b"
    assert settings.runtime.browser_timeout_ms == 45_000
    assert settings.runtime.blob_container_name == "custom-container"
    assert settings.runtime.dbt_project_dir == dbt_project_dir
    assert settings.runtime.dbt_database_path == dbt_project_dir / "custom.duckdb"
    assert settings.runtime.temp_raw_dir == temp_raw_dir
    assert settings.runtime.temp_gold_dir == temp_gold_dir
    assert settings.active_source.required_sections == ["Entertainment"]


def test_build_log_payload_keeps_metadata():
    payload = build_log_payload(
        "scrape_completed", run_id="run-123", request_id="req-456", summary_rows=2
    )
    assert payload == {
        "event": "scrape_completed",
        "run_id": "run-123",
        "request_id": "req-456",
        "summary_rows": 2,
    }
