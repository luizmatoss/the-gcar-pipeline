import os
import json
import time
import logging
import datetime
from pathlib import Path
from typing import Callable, Tuple

from azure.storage.blob import BlobServiceClient

from .scraper import scrape_page, write_jsonl
from .settings import ALLOWED_URL, RAW_DIR

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

CHECKPOINT = RAW_DIR / ".last_scrape.json"


def retry(tries: int = 3, backoff: int = 2, allowed_exceptions: Tuple = (Exception,)):
    def deco(fn: Callable):
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, tries + 1):
                try:
                    return fn(*args, **kwargs)
                except allowed_exceptions as exc:
                    last_exc = exc
                    wait = backoff ** (attempt - 1)
                    logger.warning("Attempt %s/%s failed for %s: %s — retrying in %ss", attempt, tries, fn.__name__, exc, wait)
                    time.sleep(wait)
            logger.error("All %s attempts failed for %s", tries, fn.__name__)
            raise last_exc
        return wrapper
    return deco


@retry(tries=3, backoff=2)
def safe_scrape(url: str):
    return scrape_page(url)


@retry(tries=3, backoff=2)
def safe_upload_blob(blob_client, path: Path):
    with path.open("rb") as data:
        blob_client.upload_blob(data, overwrite=True)


def load_checkpoint():
    if CHECKPOINT.exists():
        try:
            return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to read checkpoint; continuing fresh")
    return {}


def save_checkpoint(data: dict):
    try:
        CHECKPOINT.write_text(json.dumps(data), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to write checkpoint: %s", e)


def main():
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not set")

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_name = "raw-data"

    checkpoint = load_checkpoint()
    previous_scraped_at = checkpoint.get("scraped_at")

    logger.info("Starting scrape for %s", ALLOWED_URL)
    summary, features = safe_scrape(ALLOWED_URL)

    # Determine current scraped_at (guarding empty summary)
    current_scraped_at = None
    if summary:
        current_scraped_at = summary[0].get("scraped_at")

    if current_scraped_at and current_scraped_at == previous_scraped_at:
        logger.info("No new data (scraped_at unchanged). Exiting early.")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = RAW_DIR / f"summary_{timestamp}.jsonl"
    features_path = RAW_DIR / f"features_{timestamp}.jsonl"

    write_jsonl(summary, summary_path)
    write_jsonl(features, features_path)

    # Upload with retries
    blob_client_summary = blob_service_client.get_blob_client(container=container_name, blob=f"raw/summary_{timestamp}.jsonl")
    safe_upload_blob(blob_client_summary, summary_path)

    blob_client_features = blob_service_client.get_blob_client(container=container_name, blob=f"raw/features_{timestamp}.jsonl")
    safe_upload_blob(blob_client_features, features_path)

    # Save checkpoint for idempotency / incremental loads
    save_checkpoint({"scraped_at": current_scraped_at, "page_url": ALLOWED_URL, "uploaded_at": timestamp})
    logger.info("Scraping and upload complete (timestamp=%s).", timestamp)


if __name__ == "__main__":
    main()