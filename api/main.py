import logging
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from .logging_utils import configure_logging, log_event
from .models import ScrapeRequest, ScrapeResponse
from .runtime import new_run_id, raw_output_paths
from .scraper import PlaywrightTimeoutError, scrape_page, write_jsonl
from .settings import get_settings

settings = get_settings()
configure_logging(settings.runtime.log_level)
logger = logging.getLogger(__name__)


def _docs_config() -> dict[str, str | None]:
    """Configure docs routes based on runtime environment."""
    if settings.runtime.docs_enabled:
        return {
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        }
    return {"docs_url": None, "redoc_url": None, "openapi_url": None}


def _public_file_reference(path: Path) -> str:
    """Return filename only to avoid exposing server directory layout."""
    return path.name


app = FastAPI(title="TLA Green.Car Scraper", **_docs_config())


@app.post("/scrape", response_model=ScrapeResponse)
def scrape(req: ScrapeRequest):
    request_id = uuid4().hex
    url = str(req.url)
    source = settings.active_source

    if url.rstrip("/") != source.url.rstrip("/"):
        raise HTTPException(status_code=400, detail="URL not allowed")

    run_id = new_run_id()
    summary_file, features_file = raw_output_paths(settings.runtime.raw_dir, run_id)

    try:
        log_event(
            logger,
            logging.INFO,
            "scrape_request_started",
            request_id=request_id,
            run_id=run_id,
            source_id=source.source_id,
            url=url,
        )
        result = scrape_page(url, source=source, run_id=run_id)
        write_jsonl(
            result.summary, summary_file, run_id=run_id, source_id=source.source_id
        )
        write_jsonl(
            result.features, features_file, run_id=run_id, source_id=source.source_id
        )
    except PlaywrightTimeoutError as exc:
        log_event(
            logger,
            logging.ERROR,
            "scrape_timeout",
            request_id=request_id,
            run_id=run_id,
            source_id=source.source_id,
            url=url,
            error=str(exc),
        )
        raise HTTPException(status_code=504, detail="Scrape timed out") from exc
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "scrape_failed",
            request_id=request_id,
            run_id=run_id,
            source_id=source.source_id,
            url=url,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail="Scrape failed") from exc

    log_event(
        logger,
        logging.INFO,
        "scrape_request_completed",
        request_id=request_id,
        run_id=run_id,
        source_id=source.source_id,
        url=url,
        summary_rows=len(result.summary),
        feature_rows=len(result.features),
        warnings=result.warnings,
    )

    return ScrapeResponse(
        status="success",
        run_id=run_id,
        summary_file=_public_file_reference(summary_file),
        features_file=_public_file_reference(features_file),
        extracted_summary_rows=len(result.summary),
        extracted_features=len(result.features),
        warnings=result.warnings or None,
    )
