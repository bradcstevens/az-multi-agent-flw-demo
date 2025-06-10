using './main.bicep'

param solutionPrefix = readEnvironmentVariable('AZURE_ENV_NAME', 'macae')
param solutionLocation = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param azureOpenAILocation = readEnvironmentVariable('AZURE_ENV_OPENAI_LOCATION', 'swedencentral')
param enableTelemetry = bool(readEnvironmentVariable('AZURE_ENV_ENABLE_TELEMETRY', 'true'))
param logAnalyticsWorkspaceConfiguration = {
  dataRetentionInDays: 30
  existingWorkspaceResourceId: ''
}
param applicationInsightsConfiguration = {
  retentionInDays: 30
}
param virtualNetworkConfiguration = {
  enabled: false
}
param aiFoundryStorageAccountConfiguration = {
  sku: 'Standard_LRS'
}
param webServerFarmConfiguration = {
  skuCapacity: 1
  skuName: 'B2'
}
