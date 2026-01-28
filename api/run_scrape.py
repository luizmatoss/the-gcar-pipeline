import os
from pathlib import Path
import datetime
from azure.storage.blob import BlobServiceClient

from .scraper import scrape_page, write_jsonl
from .settings import ALLOWED_URL, RAW_DIR

def main():
    # Assume AZURE_STORAGE_CONNECTION_STRING is set
    connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    if not connection_string:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not set")

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_name = 'raw-data'

    # Scrape the page
    summary, features = scrape_page(ALLOWED_URL)

    # Generate timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    # Write locally (optional, for debugging)
    summary_path = RAW_DIR / f'summary_{timestamp}.jsonl'
    features_path = RAW_DIR / f'features_{timestamp}.jsonl'

    write_jsonl(summary, summary_path)
    write_jsonl(features, features_path)

    # Upload to Blob
    blob_client_summary = blob_service_client.get_blob_client(container=container_name, blob=f'raw/summary_{timestamp}.jsonl')
    with open(summary_path, 'rb') as data:
        blob_client_summary.upload_blob(data, overwrite=True)

    blob_client_features = blob_service_client.get_blob_client(container=container_name, blob=f'raw/features_{timestamp}.jsonl')
    with open(features_path, 'rb') as data:
        blob_client_features.upload_blob(data, overwrite=True)

    print("Scraping and upload to Blob complete.")

if __name__ == "__main__":
    main()