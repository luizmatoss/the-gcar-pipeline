import json

from api.run_scrape import load_checkpoint, main, save_checkpoint
from api.scraper import ScrapeResult
from api.settings import CheckpointRecord


class FakeBlobClient:
    def __init__(self, name: str):
        self.name = name
        self.uploads: list[dict[str, object]] = []

    def upload_blob(self, data, overwrite: bool):
        self.uploads.append({"bytes": data.read(), "overwrite": overwrite})


class FakeBlobServiceClient:
    def __init__(self):
        self.clients: list[dict[str, object]] = []

    def get_blob_client(self, container: str, blob: str):
        client = FakeBlobClient(blob)
        self.clients.append({"container": container, "blob": blob, "client": client})
        return client


def make_result(run_id: str, fingerprint: str) -> ScrapeResult:
    return ScrapeResult(
        run_id=run_id,
        source_id="green-car-audi-e-tron-gt",
        url="https://www.green.car/audi/e-tron-gt/saloon-electric",
        summary=[{"summary_key": "Battery", "summary_value": "93.4 kWh"}],
        features=[{"feature_name": "Heated Seats", "feature_value": "true"}],
        warnings=[],
        content_fingerprint=fingerprint,
        timings_ms={"render": 3},
    )


def test_checkpoint_round_trip(tmp_path, monkeypatch):
    checkpoint_path = tmp_path / ".last_scrape.json"
    monkeypatch.setattr("api.run_scrape.CHECKPOINT", checkpoint_path)

    record = CheckpointRecord(
        source_id="source-1",
        content_fingerprint="abc123",
        uploaded_at="2026-03-14T00:00:00+00:00",
        run_id="run-1",
    )
    save_checkpoint(record)

    loaded = load_checkpoint()
    assert loaded == record


def test_batch_skips_upload_when_fingerprint_matches(tmp_path, monkeypatch):
    checkpoint_path = tmp_path / ".last_scrape.json"
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setattr("api.run_scrape.CHECKPOINT", checkpoint_path)
    monkeypatch.setattr("api.run_scrape.settings.runtime.raw_dir", raw_dir)
    monkeypatch.setattr(
        "api.run_scrape.BlobServiceClient.from_connection_string",
        lambda _: FakeBlobServiceClient(),
    )
    monkeypatch.setattr(
        "api.run_scrape.scrape_page",
        lambda url, source, run_id: make_result(run_id, "same-fingerprint"),
    )
    monkeypatch.setattr("api.run_scrape.time.sleep", lambda _: None)

    checkpoint_path.write_text(
        json.dumps(
            {
                "source_id": "green-car-audi-e-tron-gt",
                "content_fingerprint": "same-fingerprint",
                "uploaded_at": "2026-03-14T00:00:00+00:00",
                "run_id": "previous-run",
            }
        ),
        encoding="utf-8",
    )

    fake_service = FakeBlobServiceClient()
    monkeypatch.setattr(
        "api.run_scrape.BlobServiceClient.from_connection_string",
        lambda _: fake_service,
    )

    main()

    assert fake_service.clients == []
    assert not list(raw_dir.glob("*.jsonl"))
