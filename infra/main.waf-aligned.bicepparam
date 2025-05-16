using './main.bicep'

param enableTelemetry = true
param solutionPrefix = 'thdev'
param solutionLocation = 'australiaeast'
param virtualMachineConfiguration = {
  adminUsername: 'adminuser'
  adminPassword: 'P@ssw0rd1234'
}
