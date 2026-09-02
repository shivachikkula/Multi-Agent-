@description('Shared user-assigned managed identity for the three Container Apps. Least-privilege note: this template gives one identity to all three services for simplicity; split into per-service identities if you want gateway/worker to have no Key Vault or Azure OpenAI access at all.')
param name string
param location string
param tags object = {}

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

output id string = uami.id
output principalId string = uami.properties.principalId
output clientId string = uami.properties.clientId
