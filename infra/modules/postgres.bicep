@description('Azure Database for PostgreSQL Flexible Server — replaces the docker-compose "postgres" container (the diagram\'s SQL Database (Transactional) box) with a managed, persistent instance.')
param name string
param location string
param tags object = {}
param administratorLogin string
@secure()
param administratorLoginPassword string
param databaseName string = 'agentdb'
param skuName string = 'Standard_B1ms'
param tier string = 'Burstable'
param storageSizeGB int = 32
param postgresVersion string = '16'

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: tier
  }
  properties: {
    version: postgresVersion
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    storage: {
      storageSizeGB: storageSizeGB
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: postgres
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Container Apps egress IPs aren't static/known ahead of time, so this
// opens the server to Azure's internal network only (not the public
// internet) — the standard tradeoff without deploying a VNet + private
// endpoint. Tighten this to specific outbound IPs, or move to a VNet
// integration + private DNS zone, for a stricter production setup.
resource allowAzureServices 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: postgres
  name: 'AllowAllAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

output fqdn string = postgres.properties.fullyQualifiedDomainName
output databaseName string = database.name
