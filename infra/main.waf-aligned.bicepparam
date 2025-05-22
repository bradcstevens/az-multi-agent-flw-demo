using './main.bicep'

param enableTelemetry = true
param solutionPrefix = null //Type a string value to customize the prefix for your resource names
param solutionLocation = 'australiaeast'
param virtualMachineConfiguration = {
  adminUsername: 'adminuser'
  adminPassword: 'P@ssw0rd1234'
}
