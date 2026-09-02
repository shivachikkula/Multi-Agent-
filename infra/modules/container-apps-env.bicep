@description('The Container Apps Environment all three services share — the diagram\'s Agent Orchestration Layer / Azure Container Apps box. Services in the same environment reach each other over its internal DNS (e.g. https://<app-name>.internal.<defaultDomain>).')
param name string
param location string
param tags object = {}
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string

resource environment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
  }
}

output id string = environment.id
output defaultDomain string = environment.properties.defaultDomain
