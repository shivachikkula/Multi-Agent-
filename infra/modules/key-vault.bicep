@description('RBAC-authorized Key Vault holding connection strings and API keys. Container Apps resolve these directly at container-start via native Key Vault secret references (see container-app.bicep) — no Key Vault SDK calls needed in application code for this path.')
param name string
param location string
param tags object = {}
param uamiPrincipalId string
@description('Leave false while iterating (delete + redeploy reuses the vault name immediately). Set true for a real production deployment — once true it cannot be turned back off, and the vault name is reserved for 90 days after deletion.')
param enablePurgeProtection bool = false

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: enablePurgeProtection ? true : null
  }
}

// Key Vault Secrets User built-in role: 4633458b-17de-408a-b874-0445c86b69e6
resource secretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, uamiPrincipalId, 'KeyVaultSecretsUser')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = keyVault.id
output name string = keyVault.name
output uri string = keyVault.properties.vaultUri
