import os
from pathlib import Path
import subprocess
import duckdb
from azure.storage.blob import BlobServiceClient

def main():
    connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    if not connection_string:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not set")

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_name = 'raw-data'

    # Download JSONL to /tmp/raw/
    raw_dir = Path('/tmp/raw')
    raw_dir.mkdir(parents=True, exist_ok=True)

    container_client = blob_service_client.get_container_client(container_name)
    blobs = container_client.list_blobs(name_starts_with='raw/')
    for blob in blobs:
        local_path = raw_dir / blob.name.split('/')[-1]
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob.name)
        with open(local_path, 'wb') as download_file:
            download_file.write(blob_client.download_blob().readall())

    # Set env vars for dbt
    os.environ['RAW_FEATURES_GLOB'] = str(raw_dir / 'features_*.jsonl')
    os.environ['RAW_SUMMARY_GLOB'] = str(raw_dir / 'summary_*.jsonl')

    # Run dbt build
    result = subprocess.run(['dbt', 'build'], cwd='/app/dbt', capture_output=True, text=True)
    if result.returncode != 0:
        print("dbt build failed")
        print(result.stderr)
        exit(1)

    # Export gold tables to parquet
    con = duckdb.connect('/app/dbt/greencar.duckdb')
    con.execute("EXPORT DATABASE '/tmp/gold' (FORMAT PARQUET)")

    # Upload parquet to Blob
    gold_dir = Path('/tmp/gold')
    for file in gold_dir.glob('*.parquet'):
        blob_name = f'gold/{file.name}'
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        with open(file, 'rb') as data:
            blob_client.upload_blob(data, overwrite=True)

    print("dbt job complete.")

if __name__ == "__main__":
    main()