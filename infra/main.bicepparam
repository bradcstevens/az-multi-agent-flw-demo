using './main.bicep'

param enableTelemetry = true
param solutionPrefix = null //Type a string value to customize the prefix for your resource names
param solutionLocation = 'australiaeast'
param logAnalyticsWorkspaceConfiguration = {
  dataRetentionInDays: 30
}
param applicationInsightsConfiguration = {
  retentionInDays: 30
}
param virtualNetworkConfiguration = {
  enabled: true
}
param aiFoundryStorageAccountConfiguration = {
  sku: 'Standard_LRS'
}
param webServerFarmConfiguration = {
  skuCapacity: 1
  skuName: 'B2'
}
