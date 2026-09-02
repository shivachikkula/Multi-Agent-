@description('Azure Cache for Redis — replaces the docker-compose "redis" container. Basic C0 is fine for a demo; move to Standard (replication) or Premium (VNet/private endpoint support, persistence) for production.')
param name string
param location string
param tags object = {}
param skuName string = 'Basic'
param skuFamily string = 'C'
param skuCapacity int = 0

resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      name: skuName
      family: skuFamily
      capacity: skuCapacity
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
  }
}

output hostName string = redis.properties.hostName
output sslPort int = redis.properties.sslPort
@secure()
output primaryKey string = redis.listKeys().primaryKey
