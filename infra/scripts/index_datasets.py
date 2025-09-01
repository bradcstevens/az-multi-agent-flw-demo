from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex, SimpleField, SearchField, SearchFieldDataType
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import csv
import sys
import io

if len(sys.argv) > 1:
    storage_account_name = sys.argv[1]
    blob_container_name = sys.argv[2]
    ai_search_endpoint = sys.argv[3]
    if not ai_search_endpoint.__contains__("search.windows.net"):
        ai_search_endpoint = f"https://{ai_search_endpoint}.search.windows.net"
else:
    print("Usage: python index_datasets.py <storage_account_name> <blob_container_name> <ai_search_endpoint>")
    sys.exit(1)

credential = AzureCliCredential()

blob_service_client = BlobServiceClient(account_url=f"https://{storage_account_name}.blob.core.windows.net", credential=credential)
container_client = blob_service_client.get_container_client(blob_container_name)

try:
    print("Fetching files in container...")
    blob_list = container_client.list_blobs()
except Exception as e:
    print(f"Error fetching files: {e}")
    sys.exit(1)

success_count = 0
fail_count = 0

for blob in blob_list:
    if blob.name.endswith(".csv"):
        index_name = blob.name.replace(".csv", "").lower()
        csv_data = container_client.download_blob(blob.name).readall()
        data_list = []
        try:
            print(f"Reading data from blob: {blob.name}...")
            csv_text = csv_data.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(csv_text))
            for row in csv_reader:
                data_list.append(row)
            print(f"Loaded {len(data_list)} records from CSV file - {blob.name}.")
        except Exception as e:
            print(f"Error reading CSV file - {blob.name}: {e}")
            fail_count += 1
            continue

        if not data_list:
            print(f"No data found in CSV file - {blob.name}. Skipping.")
            fail_count += 1
            continue

        headers = list(data_list[0].keys())

        index_fields = [ SimpleField(name="Id", type=SearchFieldDataType.String, key=True) ]
        for header in headers:
            index_fields.append(SearchField(name=header, type=SearchFieldDataType.String, searchable=True))

        index = SearchIndex(name=index_name, fields=index_fields)

        try:
            print("Creating or updating Azure Search index...")
            search_index_client = SearchIndexClient(endpoint=ai_search_endpoint, credential=credential)
            index_result = search_index_client.create_or_update_index(index=index)
            print(f"Index '{index_name}' created or updated successfully.")
        except Exception as e:
            print(f"Error creating/updating index: {e}")
            fail_count += 1
            continue

        for idx, item in enumerate(data_list, start=1):
            item["Id"] = str(idx)

        try:
            print("Uploading documents to the index...")
            search_client = SearchClient(endpoint=ai_search_endpoint, index_name=index_name, credential=credential)
            result = search_client.upload_documents(documents=data_list)
            print(f"Uploaded {len(data_list)} documents.")
            success_count += 1
        except Exception as e:
            print(f"Error uploading documents: {e}")
            fail_count += 1
            continue

print(f"Processing complete. Success: {success_count}, Failed: {fail_count}")