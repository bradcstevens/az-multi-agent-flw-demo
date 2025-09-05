#Requires -Version 7.0

param(
    [string]$backendUrl,
    [string]$DirectoryPath,
    [string]$StorageAccount,
    [string]$BlobContainer,
    [string]$AiSearch,
    [string]$AiSearchIndex,
    [string]$ResourceGroup
)

# Get parameters from azd env, if not provided
if (-not $backendUrl) {
    $backendUrl = $(azd env get-value BACKEND_URL)
}
if (-not $DirectoryPath) {
    $DirectoryPath = "data/agent_teams"
}
if (-not $StorageAccount) {
    $StorageAccount = $(azd env get-value AZURE_STORAGE_ACCOUNT_NAME)
}

if (-not $BlobContainer) {
    $BlobContainer = $(azd env get-value AZURE_STORAGE_CONTAINER_NAME)
}

if (-not $AiSearch) {
    $AiSearch = $(azd env get-value AZURE_AI_SEARCH_NAME)
}

if (-not $AiSearchIndex) {
    $AiSearchIndex = $(azd env get-value AZURE_AI_SEARCH_INDEX_NAME)
}

if (-not $ResourceGroup) {
    $ResourceGroup = $(azd env get-value AZURE_RESOURCE_GROUP)
}

# Check if all required arguments are provided
if (-not $backendUrl -or -not $DirectoryPath -or -not $StorageAccount -or -not $BlobContainer -or -not $AiSearch -or -not $AiSearchIndex -or -not $ResourceGroup) {
    Write-Host "Usage: .\Team-Config-And-Data.ps1 -backendUrl <backendUrl> -DirectoryPath <DirectoryPath> -StorageAccount <StorageAccount> -BlobContainer <BlobContainer> -AiSearch <AiSearch> [-AiSearchIndex <AISearchIndexName>] [-ResourceGroup <ResourceGroupName>]"
    exit 1
}

$isTeamConfigFailed = $false
$isSampleDataFailed = $false
# Upload Team Configuration
Write-Host "Uploading Team Configuration..."
try {
    .\infra\scripts\Upload-Team-Config.ps1 -backendUrl $backendUrl -DirectoryPath $DirectoryPath
} catch {
    Write-Host "Error: Uploading team configuration failed."
    $isTeamConfigFailed = $true
}

Write-Host "`n----------------------------------------"
Write-Host "----------------------------------------`n"

# Process Sample Data
Write-Host "Processing Sample Data..."
try {
    .\infra\scripts\Process-Sample-Data.ps1 -StorageAccount $StorageAccount -BlobContainer $BlobContainer -AiSearch $AiSearch -AiSearchIndex $AiSearchIndex -ResourceGroup $ResourceGroup
} catch {
    Write-Host "Error: Processing sample data failed."
    $isSampleDataFailed = $true
}

if ($isTeamConfigFailed -or $isSampleDataFailed) {
    Write-Host "`nOne or more tasks failed. Please check the error messages above."
    exit 1
} else {
    Write-Host "`nBoth team configuration upload and sample data processing completed successfully."
}
