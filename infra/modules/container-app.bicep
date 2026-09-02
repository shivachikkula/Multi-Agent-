@description('Generic Container App used for all three services (gateway/orchestrator/worker). Pulls its image via the shared managed identity (no registry password), and resolves secret env vars directly from Key Vault via native Container Apps secret references — no Key Vault SDK call needed in the app itself for these.')
param name string
param location string
param tags object = {}
param containerAppsEnvironmentId string
param uamiId string
param acrLoginServer string
param imageName string
param targetPort int
@description('true = publicly reachable (gateway); false = only reachable from inside this Container Apps Environment (orchestrator, worker)')
param external bool
param minReplicas int = 1
param maxReplicas int = 3
param cpu string = '0.5'
param memory string = '1Gi'
param keyVaultUri string
@description('Plain (non-secret) environment variables: [{ name, value }]')
param envVars array = []
@description('Env vars resolved from Key Vault at container start: [{ name, keyVaultSecretName }]')
param secretEnvVars array = []

var secrets = [for s in secretEnvVars: {
  name: toLower(replace(s.name, '_', '-'))
  keyVaultUrl: '${keyVaultUri}secrets/${s.keyVaultSecretName}'
  identity: uamiId
}]

var secretEnv = [for s in secretEnvVars: {
  name: s.name
  secretRef: toLower(replace(s.name, '_', '-'))
}]

resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uamiId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: external
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acrLoginServer
          identity: uamiId
        }
      ]
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: name
          image: imageName
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: concat(envVars, secretEnv)
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: targetPort
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scale'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output name string = containerApp.name
