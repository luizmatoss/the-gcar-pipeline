
# The Green Car Pipeline

[![CI](https://github.com/luizmatoss/the-gcar-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/luizmatoss/the-gcar-pipeline/actions/workflows/ci.yml)

This project is a data pipeline for scraping and processing electric vehicle information from Green.Car. It collects vehicle features and summaries from a specific URL, stores raw data, and transforms it into analytical layers using DBT with DuckDB.

## Architecture

The pipeline follows a layered data architecture:

- **Bronze**: Raw data extracted from scraping (JSONL).
- **Silver**: Cleaned, normalized, and deduplicated current-state data (tables).
- **Gold**: Aggregated and ready-for-consumption data (tables).

## Technologies

- **Python**: Main language.
- **FastAPI**: API to trigger scraping.
- **Playwright + BeautifulSoup**: For dynamic web page scraping.
- **DBT**: For data transformation.
- **DuckDB**: Local analytical database.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/luizmatoss/the-gcar-pipeline.git
   cd tla-greencar-pipeline
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install Playwright (for scraping):
   ```bash
   python -m playwright install
   ```
   Note: This installs browsers in headless mode, suitable for CI and local testing.

4. (Optional) Set environment variables for DBT data paths:
   Copy `.env.example` to `.env` and adjust paths as needed. Use `python-dotenv` or `direnv` to load automatically:
   ```bash
   cp .env.example .env
   # Edit .env if needed
   # Install python-dotenv: pip install python-dotenv
   # Or use direnv: brew install direnv && direnv allow
   ```
   Or set manually:
   ```bash
   export RAW_FEATURES_GLOB='../data/raw/features_*.jsonl'
   export RAW_SUMMARY_GLOB='../data/raw/summary_*.jsonl'
   ```
   Optional runtime settings for batch/container jobs:
   ```bash
   export BLOB_CONTAINER_NAME='raw-data'
   export APP_ENV='development'
   export MIN_SCRAPE_INTERVAL_SECONDS='600'
   export RATE_LIMIT_REQUESTS='20'
   export RATE_LIMIT_WINDOW_SECONDS='60'
   export DBT_PROJECT_DIR='./dbt'
   export DBT_DATABASE_PATH='./dbt/greencar.duckdb'
   export TEMP_RAW_DIR='./tmp/raw'
   export TEMP_GOLD_DIR='./tmp/gold'
   ```
   For testing with fixtures, use:
   ```bash
   export RAW_FEATURES_GLOB='../data/fixtures/features_test.jsonl'
   export RAW_SUMMARY_GLOB='../data/fixtures/summary_test.jsonl'
   ```

## Usage

### Run the API

```bash
uvicorn api.main:app --reload
```

The API will be available at `http://localhost:8000`.

### API Endpoint

- **POST /scrape**: Triggers a guarded refresh of the configured active source URL.
  - Request body: `{"url": "https://www.green.car/audi/e-tron-gt/saloon-electric"}`
  - Response: status, `run_id`, generated files, extracted row counts, optional warnings, and optional `message`.
  - Possible outcomes:
    - `200 success`: scrape executed and files were generated.
    - `200 skipped`: recent data already exists (`message="skipped_fresh_data"`).
    - `409`: another scrape is already in progress for the same source.
    - `429`: rate limit exceeded.

When `APP_ENV=production`, API docs endpoints are disabled (`/docs`, `/redoc`, `/openapi.json`).

Example with curl:
```bash
curl -X POST "http://localhost:8000/scrape" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.green.car/audi/e-tron-gt/saloon-electric"}'
```

### Run DBT

DBT version: 1.11.2 (matches CI). Profiles are configured in `dbt/profiles.yml`.

1. Navigate to the DBT folder:
   ```bash
   cd dbt
   ```

2. Run the models:
   ```bash
   dbt run --profiles-dir .
   ```

3. To run only a specific model (e.g., gold):
   ```bash
   dbt run --profiles-dir . --select gold
   ```

4. To build and test all models (recommended for local testing):
   ```bash
   dbt build --profiles-dir .
   ```

5. For testing with fixtures (sets env vars inline):
   ```bash
   RAW_FEATURES_GLOB=../data/fixtures/features_test.jsonl RAW_SUMMARY_GLOB=../data/fixtures/summary_test.jsonl dbt build --profiles-dir .
   ```

## Testing and CI

### Fixtures

This project uses test fixtures to ensure CI reliability without depending on external data sources. Fixtures are stored in `data/fixtures/` and contain sample data for:

- `features_test.jsonl`: Sample vehicle features data.
- `summary_test.jsonl`: Sample vehicle summary data.

These fixtures mirror the schema of real scraped data but with controlled, consistent content, including repeated snapshots to validate silver/gold deduplication behavior.

### CI Pipeline

The GitHub Actions CI pipeline runs on every push/PR to `main`:

1. **Unit Tests**: Runs Python unit tests with pytest.
2. **DBT Build**: Uses fixtures to build and test DBT models (bronze, silver, gold layers).
3. **Data Quality**: Validates schemas and runs automated tests defined in `schema.yml`.
4. **Container Build/Push**: ACR build-and-push workflow is currently manual (`workflow_dispatch`) until Azure credentials are configured.

To run CI locally:

```bash
# Unit tests
pytest tests/ -v

# DBT with fixtures
cd dbt
RAW_FEATURES_GLOB=../data/fixtures/features_test.jsonl RAW_SUMMARY_GLOB=../data/fixtures/summary_test.jsonl dbt build --profiles-dir .
```

### Local vs CI Differences

- **Local**: Uses real scraped data from `data/raw/` (requires scraping first).
- **CI**: Uses fixtures for fast, reliable testing without external dependencies.

## Project Structure

```
tla-greencar-pipeline/
├── api/                    # FastAPI code
│   ├── main.py            # Main endpoint
│   ├── scraper.py         # Scraping logic
│   ├── models.py          # Pydantic models
│   └── settings.py        # Settings
├── data/                  # Data
│   ├── raw/               # Raw data (JSONL)
│   └── logs/              # Execution logs
├── dbt/                   # DBT models
│   ├── models/
│   │   ├── bronze/        # Bronze layer
│   │   ├── silver/        # Silver layer
│   │   └── gold/          # Gold layer
│   ├── dbt_project.yml    # DBT config
│   └── profiles.yml       # DBT profiles
├── tools/                 # Auxiliary tools
├── requirements.txt       # Python dependencies
├── Makefile               # Build scripts
└── README.md              # This documentation
```

## Quick Validation Commands

```bash
# Lint + types + tests
ruff check api tests
mypy api tests
pytest -q
```

## Deploy Story

This repo demonstrates a complete deployment pipeline: local development → containerization → cloud deployment.

### Run Locally

1. Install dependencies and Playwright browsers:
   ```bash
   pip install -r requirements.txt
   python -m playwright install
   ```

2. Run the API:
   ```bash
   uvicorn api.main:app --reload
   ```
   Or run the scraper directly:
   ```bash
   python -m api.run_scrape
   ```

### Docker

Build and run the scraper container locally:
```bash
docker build -f Dockerfile.scraper -t greencar-scraper:latest .
docker run --rm \
  -e AZURE_STORAGE_CONNECTION_STRING="${AZURE_STORAGE_CONNECTION_STRING}" \
  -e BLOB_CONTAINER_NAME="${BLOB_CONTAINER_NAME:-raw-data}" \
  greencar-scraper:latest
```

### Deploy to Azure (Example: ACR + ACI)

1. Build, tag, and push to Azure Container Registry:
   ```bash
   az acr login --name <ACR_NAME>
   docker tag greencar-scraper:latest <ACR_NAME>.azurecr.io/greencar-scraper:latest
   docker push <ACR_NAME>.azurecr.io/greencar-scraper:latest
   ```

2. Deploy to Azure Container Instances:
   ```bash
   az container create --resource-group <RG> --name greencar-scraper \
     --image <ACR_NAME>.azurecr.io/greencar-scraper:latest \
     --environment-variables AZURE_STORAGE_CONNECTION_STRING="${AZURE_STORAGE_CONNECTION_STRING}"
   ```

For production, consider Azure Container Apps or Kubernetes for scaling and orchestration.

## Production Concerns

To make this portfolio-grade, we've implemented key production concerns:

- **Retries & Exponential Backoff**: Scraping and blob uploads retry up to 3 times with exponential backoff (implemented in `api/run_scrape.py`).
- **Idempotency / Incremental Loads**: Checkpoint file `data/.last_scrape.json` prevents re-processing and uploading duplicate data.
- **Safe Uploads**: Blob uploads use `overwrite=True` and are retried for transient failures.
- **Logging**: Structured logging for monitoring and debugging.
- **Current-State Models**: Bronze preserves snapshot history, while silver and gold expose the latest deduplicated state per business key.
- **API Abuse Guardrails**: Per-client rate limit (`429`), in-flight lock per source (`409`), and cooldown-based skip to avoid unnecessary expensive scrape runs.
- **Container Security Baseline**: Scraper and DBT images run as non-root users.
- **Monitoring & Alerts**: Recommend adding JSON logs, a healthcheck endpoint, and forwarding to Azure Monitor / Application Insights or Prometheus + Alertmanager.
- **Secrets Management**: Use Azure Key Vault or managed identity for production credentials (avoid raw env vars).

## Next Steps

- Add API authentication.
- Expand integration and smoke test coverage.
- Migrate to a cloud database / warehouse.
- Add monitoring and alerting.
- Add distributed rate limiting/locking (e.g., Redis or gateway policies) for multi-instance scaling.

## License

MIT License. See LICENSE file for details.
