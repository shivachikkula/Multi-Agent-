@description('Optional Azure OpenAI Service + a single model deployment, only created when deployAzureOpenAI=true on main.bicep. Grants the shared managed identity "Cognitive Services OpenAI User" so the orchestrator authenticates via AZURE_USE_MANAGED_IDENTITY instead of an API key.')
param name string
param location string
param tags object = {}
param uamiPrincipalId string
param modelDeploymentName string
param modelName string
param modelVersion string
param modelCapacity int = 10

resource openAI 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
  }
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-10-01-preview' = {
  parent: openAI
  name: modelDeploymentName
  sku: {
    name: 'Standard'
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

// Cognitive Services OpenAI User built-in role: 5e0bd9bd-7b93-4f28-af87-19fc36ad61bd
resource openAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAI.id, uamiPrincipalId, 'CognitiveServicesOpenAIUser')
  scope: openAI
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output endpoint string = openAI.properties.endpoint
output id string = openAI.id
