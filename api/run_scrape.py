import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Tuple

from azure.storage.blob import BlobServiceClient

from .logging_utils import configure_logging, log_event
from .runtime import new_run_id, raw_output_paths
from .scraper import ScrapeResult, scrape_page, write_jsonl
from .settings import CheckpointRecord, get_settings

settings = get_settings()
configure_logging(settings.runtime.log_level)
logger = logging.getLogger(__name__)

# Local checkpoint used to avoid re-uploading the same scrape snapshot.
CHECKPOINT = settings.runtime.raw_dir / ".last_scrape.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def retry_call(
    fn: Callable,
    *args,
    operation_name: str,
    allowed_exceptions: Tuple = (Exception,),
    **kwargs,
):
    last_exc: BaseException | None = None
    for attempt in range(1, settings.runtime.retry_tries + 1):
        try:
            return fn(*args, **kwargs)
        except allowed_exceptions as exc:
            last_exc = exc
            wait = settings.runtime.retry_backoff_seconds ** (attempt - 1)
            log_event(
                logger,
                logging.WARNING,
                "retry_attempt_failed",
                operation=operation_name,
                attempt=attempt,
                max_attempts=settings.runtime.retry_tries,
                error=str(exc),
                wait_seconds=wait,
            )
            time.sleep(wait)

    log_event(
        logger,
        logging.ERROR,
        "retry_exhausted",
        operation=operation_name,
        max_attempts=settings.runtime.retry_tries,
        error=str(last_exc),
    )
    assert last_exc is not None
    raise last_exc


def load_checkpoint() -> CheckpointRecord | None:
    if CHECKPOINT.exists():
        try:
            payload = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
            return CheckpointRecord(**payload)
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "checkpoint_read_failed",
                path=str(CHECKPOINT),
                error=str(exc),
            )
    return None


def save_checkpoint(data: CheckpointRecord):
    try:
        if hasattr(data, "model_dump_json"):
            payload = data.model_dump_json(indent=2)
        else:
            payload = data.json(indent=2)
        CHECKPOINT.write_text(payload, encoding="utf-8")
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "checkpoint_write_failed",
            path=str(CHECKPOINT),
            error=str(exc),
        )


def upload_blob(blob_client, path: Path, *, run_id: str, blob_name: str):
    with path.open("rb") as data:
        blob_client.upload_blob(data, overwrite=True)
    log_event(
        logger,
        logging.INFO,
        "blob_uploaded",
        run_id=run_id,
        blob_name=blob_name,
        path=str(path),
    )


def persist_scrape_output(result: ScrapeResult) -> tuple[Path, Path]:
    summary_path, features_path = raw_output_paths(
        settings.runtime.raw_dir, result.run_id
    )
    write_jsonl(
        result.summary, summary_path, run_id=result.run_id, source_id=result.source_id
    )
    write_jsonl(
        result.features, features_path, run_id=result.run_id, source_id=result.source_id
    )
    return summary_path, features_path


def main():
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not set")

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_name = settings.runtime.blob_container_name
    source = settings.active_source
    run_id = new_run_id()

    log_event(
        logger,
        logging.INFO,
        "batch_scrape_started",
        run_id=run_id,
        source_id=source.source_id,
        url=source.url,
    )

    checkpoint = load_checkpoint()
    result = retry_call(
        scrape_page,
        source.url,
        source,
        run_id,
        operation_name="scrape_page",
        allowed_exceptions=(Exception,),
    )

    if checkpoint and result.content_fingerprint == checkpoint.content_fingerprint:
        log_event(
            logger,
            logging.INFO,
            "batch_scrape_skipped",
            run_id=run_id,
            source_id=source.source_id,
            fingerprint=result.content_fingerprint,
            previous_run_id=checkpoint.run_id,
        )
        return

    summary_path, features_path = persist_scrape_output(result)

    summary_blob_name = f"raw/summary_{result.run_id}.jsonl"
    summary_blob_client = blob_service_client.get_blob_client(
        container=container_name, blob=summary_blob_name
    )
    retry_call(
        upload_blob,
        summary_blob_client,
        summary_path,
        operation_name="upload_summary_blob",
        run_id=result.run_id,
        blob_name=summary_blob_name,
    )

    features_blob_name = f"raw/features_{result.run_id}.jsonl"
    features_blob_client = blob_service_client.get_blob_client(
        container=container_name, blob=features_blob_name
    )
    retry_call(
        upload_blob,
        features_blob_client,
        features_path,
        operation_name="upload_features_blob",
        run_id=result.run_id,
        blob_name=features_blob_name,
    )

    save_checkpoint(
        CheckpointRecord(
            source_id=source.source_id,
            content_fingerprint=result.content_fingerprint,
            uploaded_at=_utc_now(),
            run_id=result.run_id,
        )
    )
    log_event(
        logger,
        logging.INFO,
        "batch_scrape_completed",
        run_id=result.run_id,
        source_id=source.source_id,
        summary_rows=len(result.summary),
        feature_rows=len(result.features),
        warnings=result.warnings,
    )


if __name__ == "__main__":
    main()
