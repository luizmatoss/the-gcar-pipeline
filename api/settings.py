import json
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Optional, cast

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_RAW_DIR = DATA_DIR / "raw"
DEFAULT_LOG_DIR = DATA_DIR / "logs"
DEFAULT_SOURCE_CATALOG = PROJECT_ROOT / "config" / "sources.json"
DEFAULT_DBT_PROJECT_DIR = PROJECT_ROOT / "dbt"
DEFAULT_DBT_DATABASE_PATH = DEFAULT_DBT_PROJECT_DIR / "greencar.duckdb"
DEFAULT_TMP_ROOT = PROJECT_ROOT / "tmp"
DEFAULT_TMP_RAW_DIR = DEFAULT_TMP_ROOT / "raw"
DEFAULT_TMP_GOLD_DIR = DEFAULT_TMP_ROOT / "gold"


class SourceDefinition(BaseModel):
    source_id: str
    url: str
    active: bool = True
    required_sections: List[str] = Field(default_factory=list)


class RuntimeSettings(BaseModel):
    raw_dir: Path = DEFAULT_RAW_DIR
    log_dir: Path = DEFAULT_LOG_DIR
    source_catalog_path: Path = DEFAULT_SOURCE_CATALOG
    blob_container_name: str = "raw-data"
    dbt_project_dir: Path = DEFAULT_DBT_PROJECT_DIR
    dbt_database_path: Path = DEFAULT_DBT_DATABASE_PATH
    temp_raw_dir: Path = DEFAULT_TMP_RAW_DIR
    temp_gold_dir: Path = DEFAULT_TMP_GOLD_DIR
    active_source_id: Optional[str] = None
    browser_timeout_ms: int = 30_000
    browser_wait_ms: int = 1_500
    retry_tries: int = 3
    retry_backoff_seconds: int = 2
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    app_env: Literal["development", "staging", "production"] = "development"

    @property
    def docs_enabled(self) -> bool:
        """Disable docs/openapi in production to reduce attack surface."""
        return self.app_env != "production"


class AppSettings(BaseModel):
    runtime: RuntimeSettings
    sources: List[SourceDefinition]

    @property
    def active_source(self) -> SourceDefinition:
        if self.runtime.active_source_id:
            for source in self.sources:
                if source.source_id == self.runtime.active_source_id:
                    return source
            raise ValueError(
                "Configured ACTIVE_SOURCE_ID "
                f"'{self.runtime.active_source_id}' was not found"
            )

        active_sources = [source for source in self.sources if source.active]
        if len(active_sources) != 1:
            raise ValueError(
                "Exactly one active source is required when ACTIVE_SOURCE_ID is not set"
            )
        return active_sources[0]


class CheckpointRecord(BaseModel):
    source_id: str
    content_fingerprint: str
    uploaded_at: str
    run_id: str


def _read_sources(path: Path) -> List[SourceDefinition]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = [SourceDefinition(**item) for item in payload.get("sources", [])]
    if not sources:
        raise ValueError(f"No sources found in catalog: {path}")
    return sources


def _ensure_runtime_dirs(runtime: RuntimeSettings) -> None:
    runtime.raw_dir.mkdir(parents=True, exist_ok=True)
    runtime.log_dir.mkdir(parents=True, exist_ok=True)
    runtime.temp_raw_dir.mkdir(parents=True, exist_ok=True)
    runtime.temp_gold_dir.mkdir(parents=True, exist_ok=True)


def load_settings() -> AppSettings:
    log_level = cast(
        Literal["DEBUG", "INFO", "WARNING", "ERROR"],
        os.getenv("LOG_LEVEL", "INFO").upper(),
    )
    runtime = RuntimeSettings(
        raw_dir=Path(os.getenv("RAW_DIR", DEFAULT_RAW_DIR)),
        log_dir=Path(os.getenv("LOG_DIR", DEFAULT_LOG_DIR)),
        source_catalog_path=Path(
            os.getenv("SOURCE_CATALOG_PATH", DEFAULT_SOURCE_CATALOG)
        ),
        blob_container_name=os.getenv("BLOB_CONTAINER_NAME", "raw-data"),
        dbt_project_dir=Path(os.getenv("DBT_PROJECT_DIR", DEFAULT_DBT_PROJECT_DIR)),
        dbt_database_path=Path(
            os.getenv("DBT_DATABASE_PATH", DEFAULT_DBT_DATABASE_PATH)
        ),
        temp_raw_dir=Path(os.getenv("TEMP_RAW_DIR", DEFAULT_TMP_RAW_DIR)),
        temp_gold_dir=Path(os.getenv("TEMP_GOLD_DIR", DEFAULT_TMP_GOLD_DIR)),
        active_source_id=os.getenv("ACTIVE_SOURCE_ID"),
        browser_timeout_ms=int(os.getenv("BROWSER_TIMEOUT_MS", "30000")),
        browser_wait_ms=int(os.getenv("BROWSER_WAIT_MS", "1500")),
        retry_tries=int(os.getenv("RETRY_TRIES", "3")),
        retry_backoff_seconds=int(os.getenv("RETRY_BACKOFF_SECONDS", "2")),
        log_level=log_level,
        app_env=os.getenv("APP_ENV", "development").lower(),
    )
    _ensure_runtime_dirs(runtime)
    return AppSettings(
        runtime=runtime, sources=_read_sources(runtime.source_catalog_path)
    )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return load_settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
