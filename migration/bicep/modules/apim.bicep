targetScope = 'resourceGroup'

param apimName string
param location string
param publisherEmail string
param publisherName string
param environmentProfile string
param foundryBaseUrl string
param entraTenantId string
param expectedAudience string
param requiredAppRole string
param enableClaudeDesktopDelegatedAuth bool
param claudeDesktopClientId string
param claudeDesktopDelegatedScope string
param perUserRateLimit int
param perUserTokenLimit int
param perUserConcurrentStreamLimit int
param aggregateConcurrentStreamLimit int
param apimSkuName string
param minimumCapacity int
param defaultCapacity int
param maximumCapacity int
param zoneRedundant bool
param networkingProfile string
param apimSubnetResourceId string

var capacitiesAreValid = minimumCapacity <= defaultCapacity && defaultCapacity <= maximumCapacity && (!zoneRedundant || minimumCapacity >= 2)
var validatedCapacity = capacitiesAreValid ? defaultCapacity : fail('APIM capacities must be ordered, and zone-redundant capacity must be at least two units.')
var privateNetworking = networkingProfile == 'private'
var validatedPerUserConcurrentStreamLimit = perUserConcurrentStreamLimit <= aggregateConcurrentStreamLimit ? perUserConcurrentStreamLimit : fail('Per-user concurrent streams cannot exceed the aggregate limit.')

resource apim 'Microsoft.ApiManagement/service@2025-03-01-preview' = {
  name: apimName
  location: location
  sku: {
    name: apimSkuName
    capacity: validatedCapacity
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
    publicNetworkAccess: privateNetworking ? 'Disabled' : 'Enabled'
    virtualNetworkType: privateNetworking ? 'Internal' : 'None'
    virtualNetworkConfiguration: privateNetworking ? {
      subnetResourceId: apimSubnetResourceId
    } : null
    zoneRedundant: zoneRedundant
  }
}

resource foundryBackend 'Microsoft.ApiManagement/service/backends@2024-05-01' = {
  parent: apim
  name: 'foundry-backend'
  properties: {
    protocol: 'http'
    url: foundryBaseUrl
    circuitBreaker: {
      rules: [
        {
          name: 'foundry-overload'
          failureCondition: {
            count: 3
            interval: 'PT1M'
            statusCodeRanges: [
              {
                min: 429
                max: 429
              }
              {
                min: 500
                max: 599
              }
            ]
          }
          tripDuration: 'PT1M'
          acceptRetryAfter: true
        }
      ]
    }
  }
}

var namedValues = {
  'entra-tenant-id': entraTenantId
  'expected-audience': expectedAudience
  'required-app-role': requiredAppRole
  'claude-desktop-delegated-auth-enabled': string(enableClaudeDesktopDelegatedAuth)
  'claude-desktop-client-id': claudeDesktopClientId
  'claude-desktop-delegated-scope': claudeDesktopDelegatedScope
  'per-user-rate-limit': string(perUserRateLimit)
  'per-user-token-limit': string(perUserTokenLimit)
  'per-user-concurrent-stream-limit': string(validatedPerUserConcurrentStreamLimit)
  'aggregate-concurrent-stream-limit': string(aggregateConcurrentStreamLimit)
  'environment-profile': environmentProfile
}

resource namedValue 'Microsoft.ApiManagement/service/namedValues@2024-05-01' = [for item in items(namedValues): {
  parent: apim
  name: item.key
  properties: {
    displayName: item.key
    value: item.value
    secret: false
  }
}]

resource claudeApi 'Microsoft.ApiManagement/service/apis@2024-05-01' = {
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
    apiRevision: '1'
  }
}

resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: claudeApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../../../apim/policies/claude-base.xml')
  }
}

var operations = [
  {
    name: 'messages'
    displayName: 'Create message'
    method: 'POST'
    urlTemplate: '/v1/messages'
    policy: loadTextContent('../../../apim/policies/claude-messages.xml')
  }
  {
    name: 'count-tokens'
    displayName: 'Count message tokens'
    method: 'POST'
    urlTemplate: '/v1/messages/count_tokens'
    policy: loadTextContent('../../../apim/policies/claude-count-tokens.xml')
  }
]

resource operation 'Microsoft.ApiManagement/service/apis/operations@2024-05-01' = [for item in operations: {
  parent: claudeApi
  name: item.name
  properties: {
    displayName: item.displayName
    method: item.method
    urlTemplate: item.urlTemplate
    templateParameters: []
    responses: []
  }
}]

resource operationPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2024-05-01' = [for (item, i) in operations: {
  parent: operation[i]
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: item.policy
  }
}]

resource healthOperation 'Microsoft.ApiManagement/service/apis/operations@2024-05-01' = {
  parent: claudeApi
  name: 'health'
  properties: {
    displayName: 'Gateway health'
    method: 'GET'
    urlTemplate: '/health'
    templateParameters: []
    responses: []
  }
}

resource healthPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2024-05-01' = {
  parent: healthOperation
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: '<policies><inbound><return-response><set-status code="200" reason="OK" /><set-body>healthy</set-body></return-response></inbound><backend><base /></backend><outbound><base /></outbound><on-error><base /></on-error></policies>'
  }
}

output apimPrincipalId string = apim.identity.principalId
output apimResourceId string = apim.id
output apimGatewayUrl string = 'https://${apim.name}.azure-api.net'
output apimGatewayHostname string = '${apim.name}.azure-api.net'
