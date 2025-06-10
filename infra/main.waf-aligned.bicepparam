using './main.bicep'

param solutionPrefix = readEnvironmentVariable('AZURE_ENV_NAME', 'macae')
param solutionLocation = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param azureOpenAILocation = readEnvironmentVariable('AZURE_ENV_OPENAI_LOCATION', 'swedencentral')
param enableTelemetry = bool(readEnvironmentVariable('AZURE_ENV_ENABLE_TELEMETRY', 'true'))
param virtualMachineConfiguration = {
  adminUsername: 'adminuser'
  adminPassword: 'P@ssw0rd1234'
}

param logAnalyticsWorkspaceConfiguration = {
  existingWorkspaceResourceId: ''
}
