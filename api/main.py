from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException

from .models import ScrapeRequest, ScrapeResponse
from .scraper import scrape_page, write_jsonl
from .settings import RAW_DIR, ALLOWED_URL

app = FastAPI(title="TLA Green.Car Scraper")


@app.post("/scrape", response_model=ScrapeResponse)
def scrape(req: ScrapeRequest):
    url = str(req.url)

    if url.rstrip("/") != ALLOWED_URL.rstrip("/"):
        raise HTTPException(status_code=400, detail="URL not allowed")

    summary, features = scrape_page(url)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    summary_file = RAW_DIR / f"summary_{ts}.jsonl"
    features_file = RAW_DIR / f"features_{ts}.jsonl"

    write_jsonl(summary, summary_file)
    write_jsonl(features, features_file)

    return ScrapeResponse(
        status="success",
        summary_file=str(summary_file),
        features_file=str(features_file),
        extracted_summary_rows=len(summary),
        extracted_features=len(features),
    )
