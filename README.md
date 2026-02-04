# TLA Green.Car Pipeline

[![CI](https://github.com/luizmatoss/the-gcar-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/luizmatoss/the-gcar-pipeline/actions/workflows/ci.yml)

This project is a data pipeline for scraping and processing electric vehicle information from Green.Car. It collects vehicle features and summaries from a specific URL, stores raw data, and transforms it into analytical layers using DBT with DuckDB.

## Architecture

The pipeline follows a layered data architecture:

- **Bronze**: Raw data extracted from scraping (JSONL).
- **Silver**: Cleaned and normalized data (views).
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

- **POST /scrape**: Triggers scraping of an allowed URL.
  - Request body: `{"url": "https://example.com/vehicle"}`
  - Response: Status, generated files, and extracted row counts.

Example with curl:
```bash
curl -X POST "http://localhost:8000/scrape" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://green.car/example-vehicle"}'
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

These fixtures mirror the schema of real scraped data but with controlled, consistent content.

### CI Pipeline

The GitHub Actions CI pipeline runs on every push/PR to `main`:

1. **Unit Tests**: Runs Python unit tests with pytest.
2. **DBT Build**: Uses fixtures to build and test DBT models (bronze, silver, gold layers).
3. **Data Quality**: Validates schemas and runs automated tests defined in `schema.yml`.

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

## Testing

Run unit tests with pytest:

```bash
pytest tests/
```

Or with verbose output:

```bash
pytest tests/ -v
```

### DBT Testing

For local DBT testing with fixtures:

```bash
cd dbt
RAW_FEATURES_GLOB=../data/fixtures/features_test.jsonl RAW_SUMMARY_GLOB=../data/fixtures/summary_test.jsonl dbt build --profiles-dir .
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
docker run --rm -e AZURE_STORAGE_CONNECTION_STRING="${AZURE_STORAGE_CONNECTION_STRING}" greencar-scraper:latest
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
- **Rate Limiting**: Single-page scrape with built-in delays; for multi-page, add concurrency limits.
- **Monitoring & Alerts**: Recommend adding JSON logs, a healthcheck endpoint, and forwarding to Azure Monitor / Application Insights or Prometheus + Alertmanager.
- **Secrets Management**: Use Azure Key Vault or managed identity for production credentials (avoid raw env vars).

## Next Steps

- Add API authentication.
- Implement automated tests.
- Migrate to cloud database.
- Add monitoring and structured logs.

## License

MIT License. See LICENSE file for details.

Updated on 24 January 2026 to trigger GitHub Actions.