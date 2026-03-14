from scripts.run_dbt_job import settings


def test_run_dbt_job_uses_portable_runtime_defaults():
    assert settings.runtime.blob_container_name
    assert settings.runtime.dbt_project_dir.name == "dbt"
    assert settings.runtime.dbt_database_path.name == "greencar.duckdb"
    assert settings.runtime.temp_raw_dir.name == "raw"
    assert settings.runtime.temp_gold_dir.name == "gold"
