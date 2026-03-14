from typing import List, Optional

from pydantic import BaseModel, HttpUrl


class ScrapeRequest(BaseModel):
    url: HttpUrl


class ScrapeResponse(BaseModel):
    status: str
    run_id: str
    features_file: str
    summary_file: str
    extracted_features: int
    extracted_summary_rows: int
    warnings: Optional[List[str]] = None
