from pydantic import BaseModel, HttpUrl
from typing import Optional, Literal


class ScrapeRequest(BaseModel):
    url: HttpUrl


class ScrapeResponse(BaseModel):
    status: Literal["success"]
    features_file: str
    summary_file: str
    extracted_features: int
    extracted_summary_rows: int
