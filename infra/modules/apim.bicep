targetScope = 'resourceGroup'

param apimName string
param location string
param publisherEmail string
param publisherName string
param environmentProfile string
param foundryHost string
param expectedAudience string
param perUserRateLimit int
param perUserHourlyQuota int
param perUserTokenLimit int

@allowed([
  'Developer'
  'PremiumV2'
])
var skuName = environmentProfile == 'poc' ? 'Developer' : 'PremiumV2'
var skuCapacity = 1

resource apim 'Microsoft.ApiManagement/service@2023-05-01-preview' = {
  name: apimName
  location: location
  sku: {
    name: skuName
    capacity: skuCapacity
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
  }
}

resource nvFoundryHost 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  name: '${apim.name}/foundry-host'
  properties: {
    displayName: 'foundry-host'
    value: foundryHost
    secret: false
  }
}

resource nvExpectedAudience 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  name: '${apim.name}/expected-audience'
  properties: {
    displayName: 'expected-audience'
    value: expectedAudience
    secret: false
  }
}

resource nvRateLimit 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  name: '${apim.name}/per-user-rate-limit'
  properties: {
    displayName: 'per-user-rate-limit'
    value: string(perUserRateLimit)
    secret: false
  }
}

resource nvHourlyQuota 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  name: '${apim.name}/per-user-hourly-quota'
  properties: {
    displayName: 'per-user-hourly-quota'
    value: string(perUserHourlyQuota)
    secret: false
  }
}

resource nvTokenLimit 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  name: '${apim.name}/per-user-token-limit'
  properties: {
    displayName: 'per-user-token-limit'
    value: string(perUserTokenLimit)
    secret: false
  }
}

resource nvProfile 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  name: '${apim.name}/environment-profile'
  properties: {
    displayName: 'environment-profile'
    value: environmentProfile
    secret: false
  }
}

output apimPrincipalId string = apim.identity.principalId
output apimGatewayUrl string = 'https://${apim.name}.azure-api.net'
