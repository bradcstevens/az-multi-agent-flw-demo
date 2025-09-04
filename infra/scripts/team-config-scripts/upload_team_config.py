import sys
import json
import os
from azure.identity import AzureCliCredential
from azure.cosmos import CosmosClient
from datetime import datetime
from team_service import validate_and_parse_team_config
from models import BaseDataModel

if len(sys.argv) < 4:
    print("Usage: python upload_team_config.py <cosmos_endpoint> <database_name> <container_name> <directory_path> [<user_principal_id>]")
    sys.exit(1)

cosmosdb_name = sys.argv[1]
database_name = sys.argv[2]
container_name = sys.argv[3]
directory_path = sys.argv[4]
user_principal_id = sys.argv[5] if len(sys.argv) > 5 else "00000000-0000-0000-0000-000000000000"

# Convert to absolute path if provided as relative
directory_path = os.path.abspath(directory_path)
print(f"Scanning directory: {directory_path}")

credential = AzureCliCredential()

# Create a Cosmos client
cosmos_endpoint = f"https://{cosmosdb_name}.documents.azure.com:443/"
print(f"Connecting to Cosmos DB at: {cosmos_endpoint}")
client = CosmosClient(url=cosmos_endpoint, credential=credential)

# Get or create the database
database = client.get_database_client(database_name)
print(f"Using database: {database_name}")

# Get or create the container
container = database.get_container_client(container_name)
print(f"Using container: {container_name}")

files_to_process = [
    ("hr.json", "00000000-0000-0000-0000-000000000001"),
    ("marketing.json", "00000000-0000-0000-0000-000000000002"),
    ("retail.json", "00000000-0000-0000-0000-000000000003"),
]

# Process each JSON file in the directory
uploaded_count = 0
for filename, team_id in files_to_process:
    file_path = os.path.join(directory_path, filename)
    if os.path.isfile(file_path):
        print(f"Processing file: {filename}")
        try:
            with open(file_path, 'r') as file:
                team_config_data = json.load(file)
            
            validated_team_config: BaseDataModel = validate_and_parse_team_config(team_config_data, user_principal_id, team_id)
            item = validated_team_config.model_dump()

            for key, value in list(item.items()):
                if isinstance(value, datetime):
                    item[key] = value.isoformat()

            container.upsert_item(item)
            print(f"Successfully uploaded team configuration with Id: {item['id']}, team_id: {team_id}")
            uploaded_count += 1
            
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in file {filename}")
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
    else:
        print(f"File not found: {filename}")

print(f"Completed uploading {uploaded_count} team configurations")