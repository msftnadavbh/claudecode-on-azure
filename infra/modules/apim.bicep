targetScope = 'resourceGroup'

param apimName string
param location string
param publisherEmail string
param publisherName string
param environmentProfile string
param foundryBaseUrl string
param expectedAudience string
param requiredAppRole string
param perUserRateLimit int
param perUserHourlyQuota int
param perUserTokenLimit int

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

resource nvFoundryBaseUrl 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  parent: apim
  name: 'foundry-base-url'
  properties: {
    displayName: 'foundry-base-url'
    value: foundryBaseUrl
    secret: false
  }
}

resource nvExpectedAudience 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  parent: apim
  name: 'expected-audience'
  properties: {
    displayName: 'expected-audience'
    value: expectedAudience
    secret: false
  }
}

resource nvRequiredAppRole 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  parent: apim
  name: 'required-app-role'
  properties: {
    displayName: 'required-app-role'
    value: requiredAppRole
    secret: false
  }
}

resource nvRateLimit 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  parent: apim
  name: 'per-user-rate-limit'
  properties: {
    displayName: 'per-user-rate-limit'
    value: string(perUserRateLimit)
    secret: false
  }
}

resource nvHourlyQuota 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  parent: apim
  name: 'per-user-hourly-quota'
  properties: {
    displayName: 'per-user-hourly-quota'
    value: string(perUserHourlyQuota)
    secret: false
  }
}

resource nvTokenLimit 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  parent: apim
  name: 'per-user-token-limit'
  properties: {
    displayName: 'per-user-token-limit'
    value: string(perUserTokenLimit)
    secret: false
  }
}

resource nvProfile 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  parent: apim
  name: 'environment-profile'
  properties: {
    displayName: 'environment-profile'
    value: environmentProfile
    secret: false
  }
}

resource claudeApi 'Microsoft.ApiManagement/service/apis@2023-05-01-preview' = {
  parent: apim
  name: 'claude'
  properties: {
    displayName: 'Claude Messages API'
    path: 'claude'
    protocols: [
      'https'
    ]
    subscriptionRequired: false
    type: 'http'
  }
}

resource messagesOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: claudeApi
  name: 'messages'
  properties: {
    displayName: 'Create message'
    method: 'POST'
    urlTemplate: '/v1/messages'
    templateParameters: []
    responses: []
  }
}

resource messagesPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2023-05-01-preview' = {
  parent: messagesOperation
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../../apim/policies/claude-messages.xml')
  }
}

output apimPrincipalId string = apim.identity.principalId
output apimGatewayUrl string = 'https://${apim.name}.azure-api.net'
