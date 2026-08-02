// Preflight probe: does subscription policy permit resources with public network
// access enabled? Used by scripts/preflight/check-azure-subscription.sh --probe.
//
// This template is never deployed. It is submitted to `az deployment group validate`,
// which runs full policy evaluation, and the temporary resource group is deleted
// afterwards. It covers the four accelerator resource types most likely to be caught
// by a public-network-access Deny policy.

param location string = resourceGroup().location

@description('Random suffix keeping the probe resource names globally unique.')
param suffix string

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'stprobe${suffix}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    publicNetworkAccess: 'Enabled'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: 'aiprobe${suffix}'
  location: location
  sku: { name: 'S0' }
  kind: 'AIServices'
  identity: { type: 'SystemAssigned' }
  properties: {
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
    customSubDomainName: 'aiprobe${suffix}'
  }
}

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: 'srchprobe${suffix}'
  location: location
  sku: { name: 'basic' }
  identity: { type: 'SystemAssigned' }
  properties: {
    publicNetworkAccess: 'enabled'
    disableLocalAuth: true
  }
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: 'cosprobe${suffix}'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
  }
}
