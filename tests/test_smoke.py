import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
from fastapi.testclient import TestClient

from api.main import app, settings

FIXTURE_HTML = Path(__file__).parent / "fixtures" / "green_car_vehicle.html"


def test_smoke_api_to_gold_models(tmp_path, monkeypatch):
    # Keep smoke-test artifacts isolated from normal local raw files.
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    monkeypatch.setattr(settings.runtime, "raw_dir", raw_dir)
    monkeypatch.setattr(
        "api.scraper._get_rendered_html",
        lambda url: FIXTURE_HTML.read_text(encoding="utf-8"),
    )

    client = TestClient(app)

    # Exercise the real scrape endpoint with a stable HTML fixture.
    response = client.post("/scrape", json={"url": settings.active_source.url})

    assert response.status_code == 200
    payload = response.json()

    summary_file = Path(payload["summary_file"])
    features_file = Path(payload["features_file"])

    assert payload["status"] == "success"
    assert payload["run_id"]
    assert summary_file.exists()
    assert features_file.exists()

    dbt_dir = Path(__file__).resolve().parents[1] / "dbt"
    env = os.environ.copy()
    env["RAW_SUMMARY_GLOB"] = str(summary_file)
    env["RAW_FEATURES_GLOB"] = str(features_file)
    dbt_executable = shutil.which("dbt") or str(Path(sys.executable).with_name("dbt"))

    # Run only the minimum dbt path needed to prove the pipeline is alive.
    result = subprocess.run(
        [
            dbt_executable,
            "run",
            "--profiles-dir",
            ".",
            "--select",
            "+vehicle_summary +vehicle_features",
        ],
        cwd=dbt_dir,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    con = duckdb.connect(str(dbt_dir / "greencar.duckdb"))

    summary_row = con.execute("select count(*) from vehicle_summary").fetchone()
    features_row = con.execute("select count(*) from vehicle_features").fetchone()

    assert summary_row is not None
    assert features_row is not None

    vehicle_summary_count = summary_row[0]
    vehicle_features_count = features_row[0]

    assert vehicle_summary_count > 0
    assert vehicle_features_count > 0
