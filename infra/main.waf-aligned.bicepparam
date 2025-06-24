using './main.bicep'

param solutionPrefix = readEnvironmentVariable('AZURE_ENV_NAME', 'macae')
param solutionLocation = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param azureOpenAILocation = readEnvironmentVariable('AZURE_ENV_OPENAI_LOCATION', 'swedencentral')
param modelDeploymentType = readEnvironmentVariable('AZURE_ENV_MODEL_DEPLOYMENT_TYPE', 'GlobalStandard')
param gptModelName = readEnvironmentVariable('AZURE_ENV_MODEL_NAME', 'gpt-4o')
param gptModelVersion = readEnvironmentVariable('AZURE_ENV_MODEL_VERSION', '2024-08-06')
param imageTag = readEnvironmentVariable('AZURE_ENV_IMAGETAG', 'latest')
param enableTelemetry = bool(readEnvironmentVariable('AZURE_ENV_ENABLE_TELEMETRY', 'true'))
param virtualMachineConfiguration = {
  adminUsername: 'adminuser'
  adminPassword: 'P@ssw0rd1234'
}

param logAnalyticsWorkspaceConfiguration = {
  existingWorkspaceResourceId: ''
}
