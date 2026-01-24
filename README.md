# TLA Green.Car Pipeline

[![CI](https://github.com/luizmatoss/tla-greencar-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/luizmatoss/tla-greencar-pipeline/actions/workflows/ci.yml)

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
   git clone <repo-url>
   cd tla-greencar-pipeline
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install Playwright (for scraping):
   ```bash
   playwright install
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

4. Check tests (if any):
   ```bash
   dbt test --profiles-dir .
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
dbt build --profiles-dir . --vars '{"raw_features_glob":"../data/fixtures/features_test.jsonl","raw_summary_glob":"../data/fixtures/summary_test.jsonl"}'
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
dbt build --profiles-dir . --vars '{"raw_features_glob":"../data/fixtures/features_test.jsonl","raw_summary_glob":"../data/fixtures/summary_test.jsonl"}'
```

## Next Steps

- Add API authentication.
- Implement automated tests.
- Migrate to cloud database.
- Add monitoring and structured logs.

## License

[Add license here, e.g., MIT]

Updated on 24 January 2026 to trigger GitHub Actions.