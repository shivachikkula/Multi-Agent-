targetScope = 'resourceGroup'

@description('Short name used to build resource names (lowercase letters/digits only, e.g. "multiagent"). Keep it short — some derived names are length-limited (Container Registry, Key Vault).')
@minLength(3)
@maxLength(12)
param environmentName string = 'multiagent'

param location string = resourceGroup().location

@description('PostgreSQL administrator login username.')
param postgresAdminLogin string = 'agentadmin'

@description('PostgreSQL administrator password. Pass this explicitly (--parameters postgresAdminPassword=...) — there is no default.')
@secure()
@minLength(8)
param postgresAdminPassword string

@description('Initial gateway API key, stored in Key Vault as "gateway-api-key". Defaults to a fresh random GUID on every deployment that does not pass this explicitly — pin an explicit value across redeploys if existing clients depend on a stable key.')
@secure()
param gatewayApiKey string = newGuid()

@description('Image tag to deploy for all three services. Build and push images with this tag first — see infra/README.md.')
param imageTag string = 'latest'

@description('Also deploy Azure OpenAI + a model deployment, and wire the orchestrator to use it via managed identity instead of the offline mock LLM. Requires your subscription to have Azure OpenAI access.')
param deployAzureOpenAI bool = false

@description('Region for Azure OpenAI — only used when deployAzureOpenAI=true. Must be a region where the chosen model is available; can differ from `location`.')
param azureOpenAILocation string = 'eastus2'

param azureOpenAIModelDeploymentName string = 'gpt-4o'
param azureOpenAIModelName string = 'gpt-4o'
param azureOpenAIModelVersion string = '2024-08-06'

@description('Set true for a real production deployment of Key Vault (irreversible — see modules/key-vault.bicep).')
param enableKeyVaultPurgeProtection bool = false

param minReplicas int = 1
param maxReplicas int = 3

param tags object = {
  application: 'multi-agent-platform'
}

// --- Derived resource names ------------------------------------------------
// uniqueString() keeps globally-unique resource names (ACR, Key Vault,
// Postgres, Redis) stable across repeat deployments to the same resource
// group instead of colliding with other deployments/subscriptions.
var resourceToken = toLower(uniqueString(subscription().subscriptionId, resourceGroup().id, environmentName))
var alnumEnvironmentName = toLower(replace(environmentName, '-', ''))

var acrName = take('acr${alnumEnvironmentName}${resourceToken}', 50) // Container Registry: alphanumeric only
var keyVaultName = take('kv-${environmentName}-${resourceToken}', 24)
var postgresServerName = take('pg-${environmentName}-${resourceToken}', 63)
var redisName = take('redis-${environmentName}-${resourceToken}', 63)
var logAnalyticsName = 'log-${environmentName}-${resourceToken}'
var appInsightsName = 'appi-${environmentName}-${resourceToken}'
var containerAppsEnvName = 'cae-${environmentName}-${resourceToken}'
var uamiName = 'id-${environmentName}-${resourceToken}'
var openAIName = take('oai-${environmentName}-${resourceToken}', 24)

var gatewayAppName = take('${environmentName}-gateway', 32)
var orchestratorAppName = take('${environmentName}-orchestrator', 32)
var workerAppName = take('${environmentName}-worker', 32)

// --- Identity, observability, registry, secrets -----------------------------
module uami 'modules/identity.bicep' = {
  name: 'uami'
  params: {
    name: uamiName
    location: location
    tags: tags
  }
}

module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'log-analytics'
  params: {
    name: logAnalyticsName
    appInsightsName: appInsightsName
    location: location
    tags: tags
  }
}

module acr 'modules/container-registry.bicep' = {
  name: 'acr'
  params: {
    name: acrName
    location: location
    tags: tags
    uamiPrincipalId: uami.outputs.principalId
  }
}

module keyVault 'modules/key-vault.bicep' = {
  name: 'key-vault'
  params: {
    name: keyVaultName
    location: location
    tags: tags
    uamiPrincipalId: uami.outputs.principalId
    enablePurgeProtection: enableKeyVaultPurgeProtection
  }
}

// --- Data plane: Postgres + Redis (replace the docker-compose containers) --
module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    name: postgresServerName
    location: location
    tags: tags
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
  }
}

module redis 'modules/redis.bicep' = {
  name: 'redis'
  params: {
    name: redisName
    location: location
    tags: tags
  }
}

// --- Optional: Azure OpenAI --------------------------------------------------
module openai 'modules/openai.bicep' = if (deployAzureOpenAI) {
  name: 'openai'
  params: {
    name: openAIName
    location: azureOpenAILocation
    tags: tags
    uamiPrincipalId: uami.outputs.principalId
    modelDeploymentName: azureOpenAIModelDeploymentName
    modelName: azureOpenAIModelName
    modelVersion: azureOpenAIModelVersion
  }
}

// --- Secrets: written once here, resolved into containers via native --------
// Container Apps Key Vault secret references (see modules/container-app.bicep)
// Referenced by the statically-known `keyVaultName` var (not the module's
// output) — a child resource's `parent` must be resolvable before the
// deployment starts, and a module output only resolves at deploy time.
resource keyVaultRef 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
  dependsOn: [
    keyVault
  ]
}

resource secretSqlDatabaseUrl 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVaultRef
  name: 'sql-database-url'
  properties: {
    // asyncpg + Azure Postgres Flexible Server requires TLS; ?ssl=true makes
    // SQLAlchemy's asyncpg dialect enable it with default cert verification.
    value: 'postgresql+asyncpg://${postgresAdminLogin}:${uriComponent(postgresAdminPassword)}@${postgres.outputs.fqdn}:5432/${postgres.outputs.databaseName}?ssl=true'
  }
}

resource secretRedisUrl 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVaultRef
  name: 'redis-url'
  properties: {
    // rediss:// (TLS) — Azure Cache for Redis rejects plaintext by default.
    value: 'rediss://:${uriComponent(redis.outputs.primaryKey)}@${redis.outputs.hostName}:${redis.outputs.sslPort}/0'
  }
}

resource secretGatewayApiKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVaultRef
  name: 'gateway-api-key'
  properties: {
    value: gatewayApiKey
  }
}

resource secretAppInsightsConnectionString 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVaultRef
  name: 'appinsights-connection-string'
  properties: {
    value: logAnalytics.outputs.appInsightsConnectionString
  }
}

// --- Container Apps Environment ---------------------------------------------
module containerAppsEnv 'modules/container-apps-env.bicep' = {
  name: 'container-apps-env'
  params: {
    name: containerAppsEnvName
    location: location
    tags: tags
    logAnalyticsCustomerId: logAnalytics.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: logAnalytics.outputs.logAnalyticsSharedKey
  }
}

// --- Services -----------------------------------------------------------
var commonEnv = [
  { name: 'LOG_LEVEL', value: 'INFO' }
]

var openAIEnv = deployAzureOpenAI ? [
  { name: 'AZURE_OPENAI_ENDPOINT', value: openai.?outputs.?endpoint ?? '' }
  { name: 'AZURE_OPENAI_DEPLOYMENT', value: azureOpenAIModelDeploymentName }
  { name: 'AZURE_USE_MANAGED_IDENTITY', value: 'true' }
  { name: 'AZURE_CLIENT_ID', value: uami.outputs.clientId }
] : []

module orchestratorApp 'modules/container-app.bicep' = {
  name: 'orchestrator-app'
  params: {
    name: orchestratorAppName
    location: location
    tags: tags
    containerAppsEnvironmentId: containerAppsEnv.outputs.id
    uamiId: uami.outputs.id
    acrLoginServer: acr.outputs.loginServer
    imageName: '${acr.outputs.loginServer}/multiagent/orchestrator:${imageTag}'
    targetPort: 8001
    external: false // reachable only from inside this Container Apps Environment (the gateway)
    minReplicas: minReplicas
    maxReplicas: maxReplicas
    keyVaultUri: keyVault.outputs.uri
    envVars: concat(commonEnv, openAIEnv, [
      { name: 'OTEL_SERVICE_NAME', value: 'orchestrator' }
      { name: 'HITL_FINANCE_APPROVAL_THRESHOLD_USD', value: '1000' }
    ])
    secretEnvVars: [
      { name: 'SQL_DATABASE_URL', keyVaultSecretName: 'sql-database-url' }
      { name: 'REDIS_URL', keyVaultSecretName: 'redis-url' }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', keyVaultSecretName: 'appinsights-connection-string' }
    ]
  }
  dependsOn: [
    secretSqlDatabaseUrl
    secretRedisUrl
    secretAppInsightsConnectionString
  ]
}

module gatewayApp 'modules/container-app.bicep' = {
  name: 'gateway-app'
  params: {
    name: gatewayAppName
    location: location
    tags: tags
    containerAppsEnvironmentId: containerAppsEnv.outputs.id
    uamiId: uami.outputs.id
    acrLoginServer: acr.outputs.loginServer
    imageName: '${acr.outputs.loginServer}/multiagent/gateway:${imageTag}'
    targetPort: 8000
    external: true // the only publicly reachable service
    minReplicas: minReplicas
    maxReplicas: maxReplicas
    keyVaultUri: keyVault.outputs.uri
    envVars: concat(commonEnv, [
      { name: 'OTEL_SERVICE_NAME', value: 'gateway' }
      { name: 'GATEWAY_RATE_LIMIT_PER_MINUTE', value: '60' }
      { name: 'ORCHESTRATOR_BASE_URL', value: 'https://${orchestratorApp.outputs.fqdn}' }
    ])
    secretEnvVars: [
      { name: 'GATEWAY_API_KEYS', keyVaultSecretName: 'gateway-api-key' }
      { name: 'REDIS_URL', keyVaultSecretName: 'redis-url' }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', keyVaultSecretName: 'appinsights-connection-string' }
    ]
  }
  dependsOn: [
    secretGatewayApiKey
    secretRedisUrl
    secretAppInsightsConnectionString
  ]
}

module workerApp 'modules/container-app.bicep' = {
  name: 'worker-app'
  params: {
    name: workerAppName
    location: location
    tags: tags
    containerAppsEnvironmentId: containerAppsEnv.outputs.id
    uamiId: uami.outputs.id
    acrLoginServer: acr.outputs.loginServer
    imageName: '${acr.outputs.loginServer}/multiagent/worker:${imageTag}'
    targetPort: 8002
    external: false
    // Pinned to 1 replica: the worker's Redis Streams consumer name is
    // currently fixed ("worker-1" in core/events/local_queue.py), so
    // multiple replicas would collide as the same consumer. Fix that
    // in code (derive the consumer name from the pod, e.g. HOSTNAME)
    // before raising this.
    minReplicas: 1
    maxReplicas: 1
    keyVaultUri: keyVault.outputs.uri
    envVars: concat(commonEnv, [
      { name: 'OTEL_SERVICE_NAME', value: 'worker' }
    ])
    secretEnvVars: [
      { name: 'REDIS_URL', keyVaultSecretName: 'redis-url' }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', keyVaultSecretName: 'appinsights-connection-string' }
    ]
  }
  dependsOn: [
    secretRedisUrl
    secretAppInsightsConnectionString
  ]
}

// --- Outputs -----------------------------------------------------------
// No secrets are output here on purpose — fetch them from Key Vault
// directly (see infra/README.md) rather than reading them out of the
// deployment's output/history.
output gatewayUrl string = 'https://${gatewayApp.outputs.fqdn}'
output containerRegistryLoginServer string = acr.outputs.loginServer
output keyVaultName string = keyVault.outputs.name
output resourceGroupName string = resourceGroup().name
