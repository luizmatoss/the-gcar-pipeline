import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request

from .logging_utils import configure_logging, log_event
from .models import ScrapeRequest, ScrapeResponse
from .runtime import new_run_id, raw_output_paths
from .scraper import PlaywrightTimeoutError, scrape_page, write_jsonl
from .settings import get_settings

settings = get_settings()
configure_logging(settings.runtime.log_level)
logger = logging.getLogger(__name__)
_rate_lock = Lock()
_source_lock = Lock()
_request_window: dict[str, list[float]] = {}
_inflight_sources: set[str] = set()


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


def _utc_now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _client_id(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check_rate_limit(request: Request) -> None:
    now = time.time()
    window_start = now - settings.runtime.rate_limit_window_seconds
    client = _client_id(request)

    with _rate_lock:
        recent = [t for t in _request_window.get(client, []) if t >= window_start]
        if len(recent) >= settings.runtime.rate_limit_requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        recent.append(now)
        _request_window[client] = recent


def _get_latest_scrape_mtime() -> float | None:
    summary_files = sorted(settings.runtime.raw_dir.glob("summary_*.jsonl"))
    if not summary_files:
        return None
    return summary_files[-1].stat().st_mtime


_docs = _docs_config()
app = FastAPI(
    title="TLA Green.Car Scraper",
    docs_url=_docs["docs_url"],
    redoc_url=_docs["redoc_url"],
    openapi_url=_docs["openapi_url"],
)


@app.post("/scrape", response_model=ScrapeResponse)
def scrape(req: ScrapeRequest, request: Request):
    request_id = uuid4().hex
    url = str(req.url)
    source = settings.active_source

    _check_rate_limit(request)

    if url.rstrip("/") != source.url.rstrip("/"):
        raise HTTPException(status_code=400, detail="URL not allowed")

    with _source_lock:
        if source.source_id in _inflight_sources:
            raise HTTPException(
                status_code=409, detail="Scrape already running for this source"
            )
        _inflight_sources.add(source.source_id)

    try:
        latest_mtime = _get_latest_scrape_mtime()
        if latest_mtime is not None:
            age_seconds = _utc_now_ts() - latest_mtime
            if age_seconds < settings.runtime.min_scrape_interval_seconds:
                return ScrapeResponse(
                    status="skipped",
                    run_id="",
                    summary_file="",
                    features_file="",
                    extracted_summary_rows=0,
                    extracted_features=0,
                    message="skipped_fresh_data",
                )

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
                result.features,
                features_file,
                run_id=run_id,
                source_id=source.source_id,
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
    finally:
        with _source_lock:
            _inflight_sources.discard(source.source_id)
