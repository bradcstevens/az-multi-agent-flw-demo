#!/bin/bash

# Variables
backendUrl=$1
directoryPath=$2
storageAccount="$3"
blobContainer="$4"
aiSearch="$5"
aiSearchIndex="$6"
resourceGroup="$7"

# get parameters from azd env, if not provided as arguments
if [ -z "$directoryPath" ]; then
    directoryPath="data/agent_teams"
fi

if [ -z "$backendUrl" ]; then
    backendUrl=$(azd env get-value BACKEND_URL)
fi

if [ -z "$storageAccount" ]; then
    storageAccount=$(azd env get-value AZURE_STORAGE_ACCOUNT_NAME)
fi

if [ -z "$blobContainer" ]; then
    blobContainer=$(azd env get-value AZURE_STORAGE_CONTAINER_NAME)
fi

if [ -z "$aiSearch" ]; then
    aiSearch=$(azd env get-value AZURE_AI_SEARCH_NAME)
fi

if [ -z "$aiSearchIndex" ]; then
    aiSearchIndex=$(azd env get-value AZURE_AI_SEARCH_INDEX_NAME)
fi

if [ -z "$resourceGroup" ]; then
    resourceGroup=$(azd env get-value AZURE_RESOURCE_GROUP)
fi

# Check if all required arguments are provided
if [ -z "$backendUrl" ] || [ -z "$directoryPath" ] || [ -z "$storageAccount" ] || [ -z "$blobContainer" ] || [ -z "$aiSearch" ]; then
    echo "Usage: $0 <backendUrl> <directoryPath> <StorageAccountName> <StorageContainerName> <AISearchName> [AISearchIndexName] [ResourceGroupName]"
    exit 1
fi


isTeamConfigFailed=false
isSampleDataFailed=false

echo "Uploading team configuration..."
bash upload_team_config.sh "$backendUrl" "$directoryPath"
if [ $? -ne 0 ]; then
    echo "Error: Team configuration upload failed."
    isTeamConfigFailed=true
fi

echo ""
echo "----------------------------------------"
echo "----------------------------------------"
echo ""

echo "Processing sample data..."
bash process_sample_data.sh "$storageAccount" "$blobContainer" "$aiSearch" "$aiSearchIndex" "$resourceGroup"
if [ $? -ne 0 ]; then
    echo "Error: Sample data processing failed."
    isSampleDataFailed=true
fi

if [ "$isTeamConfigFailed" = true ] || [ "$isSampleDataFailed" = true ]; then
    echo "One or more processes failed."
    exit 1
fi

echo "Both team configuration upload and sample data processing completed successfully."