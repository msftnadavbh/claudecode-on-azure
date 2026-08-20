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
param perUserRateLimit int
param perUserHourlyQuota int
param perUserTokenLimit int
param apimSkuName string
param minimumCapacity int
param defaultCapacity int
param maximumCapacity int
param autoscaleEnabled bool
param scaleOutCpuThreshold int
param scaleInCpuThreshold int
param zoneRedundant bool
param networkingProfile string
param apimSubnetResourceId string
param apimPrivateEndpointSubnetResourceId string
param apimPrivateDnsZoneResourceId string
param observabilityEnabled bool
param actionGroupResourceId string

var availabilityZones = [
  '1'
  '2'
  '3'
]
var zoneCount = length(availabilityZones)
var capacityIncrement = zoneRedundant ? zoneCount : 1
var capacitiesAreOrdered = minimumCapacity <= defaultCapacity && defaultCapacity <= maximumCapacity
var capacitiesMatchZones = minimumCapacity >= zoneCount && minimumCapacity % zoneCount == 0 && defaultCapacity % zoneCount == 0 && maximumCapacity % zoneCount == 0
var capacitiesAreValid = capacitiesAreOrdered && (!zoneRedundant || capacitiesMatchZones)
var validatedCapacities = capacitiesAreValid ? {
  minimum: minimumCapacity
  default: defaultCapacity
  maximum: maximumCapacity
} : fail('APIM capacities must be ordered and, when zone redundancy is enabled, at least three and multiples of three.')
var privateNetworking = networkingProfile == 'private'
var alertActions = empty(actionGroupResourceId) ? [] : [
  {
    actionGroupId: actionGroupResourceId
  }
]

resource apim 'Microsoft.ApiManagement/service@2024-05-01' = {
  name: apimName
  location: location
  zones: zoneRedundant ? availabilityZones : null
  sku: {
    name: apimSkuName
    capacity: validatedCapacities.default
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
    publicNetworkAccess: privateNetworking ? 'Disabled' : 'Enabled'
    virtualNetworkType: privateNetworking ? 'External' : 'None'
    virtualNetworkConfiguration: privateNetworking ? {
      subnetResourceId: apimSubnetResourceId
    } : null
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
  'per-user-rate-limit': string(perUserRateLimit)
  'per-user-hourly-quota': string(perUserHourlyQuota)
  'per-user-token-limit': string(perUserTokenLimit)
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

var operations = [
  {
    name: 'messages'
    displayName: 'Create message'
    method: 'POST'
    urlTemplate: '/v1/messages'
  }
  {
    name: 'count-tokens'
    displayName: 'Count message tokens'
    method: 'POST'
    urlTemplate: '/v1/messages/count_tokens'
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
    value: loadTextContent('../../apim/policies/claude-messages.xml')
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

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (observabilityEnabled) {
  name: '${apimName}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = if (observabilityEnabled) {
  name: '${apimName}-insights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    DisableIpMasking: false
    IngestionMode: 'LogAnalytics'
  }
}

resource appInsightsLogger 'Microsoft.ApiManagement/service/loggers@2024-05-01' = if (observabilityEnabled) {
  parent: apim
  name: 'application-insights'
  properties: {
    loggerType: 'applicationInsights'
    isBuffered: false
    credentials: {
      instrumentationKey: appInsights!.properties.InstrumentationKey
      connectionString: appInsights!.properties.ConnectionString
    }
  }
}

resource apiDiagnostic 'Microsoft.ApiManagement/service/apis/diagnostics@2024-05-01' = if (observabilityEnabled) {
  parent: claudeApi
  name: 'applicationinsights'
  properties: {
    loggerId: appInsightsLogger.id
    alwaysLog: 'allErrors'
    logClientIp: false
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    frontend: {
      request: {
        body: {
          bytes: 0
        }
        headers: []
      }
      response: {
        body: {
          bytes: 0
        }
        headers: []
      }
    }
    backend: {
      request: {
        body: {
          bytes: 0
        }
        headers: []
      }
      response: {
        body: {
          bytes: 0
        }
        headers: []
      }
    }
  }
}

resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (observabilityEnabled) {
  name: 'send-to-log-analytics'
  scope: apim
  properties: {
    workspaceId: workspace.id
    logs: [
      {
        categoryGroup: 'audit'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

resource autoscale 'Microsoft.Insights/autoscalesettings@2022-10-01' = if (autoscaleEnabled) {
  name: '${apimName}-autoscale'
  location: location
  properties: {
    enabled: true
    targetResourceUri: apim.id
    profiles: [
      {
        name: 'cpu-capacity'
        capacity: {
          minimum: string(validatedCapacities.minimum)
          default: string(validatedCapacities.default)
          maximum: string(validatedCapacities.maximum)
        }
        rules: [
          {
            metricTrigger: {
              metricName: 'CpuPercentage'
              metricResourceUri: apim.id
              operator: 'GreaterThan'
              statistic: 'Average'
              threshold: scaleOutCpuThreshold
              timeAggregation: 'Average'
              timeGrain: 'PT1M'
              timeWindow: 'PT10M'
            }
            scaleAction: {
              cooldown: 'PT10M'
              direction: 'Increase'
              type: 'ChangeCount'
              value: string(capacityIncrement)
            }
          }
          {
            metricTrigger: {
              metricName: 'CpuPercentage'
              metricResourceUri: apim.id
              operator: 'LessThan'
              statistic: 'Average'
              threshold: scaleInCpuThreshold
              timeAggregation: 'Average'
              timeGrain: 'PT1M'
              timeWindow: 'PT20M'
            }
            scaleAction: {
              cooldown: 'PT20M'
              direction: 'Decrease'
              type: 'ChangeCount'
              value: string(capacityIncrement)
            }
          }
        ]
      }
    ]
  }
}

resource capacityAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (observabilityEnabled) {
  name: '${apimName}-high-capacity'
  location: 'global'
  properties: {
    description: 'APIM gateway CPU capacity is sustained above the scale-out threshold.'
    severity: 2
    enabled: true
    scopes: [
      apim.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighCpu'
          metricName: 'CpuPercentage'
          metricNamespace: 'Microsoft.ApiManagement/service'
          operator: 'GreaterThan'
          threshold: scaleOutCpuThreshold
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: alertActions
  }
}

resource failureAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (observabilityEnabled) {
  name: '${apimName}-gateway-errors'
  location: 'global'
  properties: {
    description: 'APIM reports sustained failed gateway requests.'
    severity: 1
    enabled: true
    scopes: [
      apim.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'FailedRequests'
          metricName: 'Requests'
          metricNamespace: 'Microsoft.ApiManagement/service'
          dimensions: [
            {
              name: 'BackendResponseCode'
              operator: 'Include'
              values: [
                '401'
                '403'
                '429'
                '500'
                '502'
                '503'
              ]
            }
          ]
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: alertActions
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = if (privateNetworking) {
  name: '${apimName}-gateway-pe'
  location: location
  properties: {
    subnet: {
      id: apimPrivateEndpointSubnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: 'gateway'
        properties: {
          privateLinkServiceId: apim.id
          groupIds: [
            'Gateway'
          ]
        }
      }
    ]
  }
}

resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (privateNetworking && !empty(apimPrivateDnsZoneResourceId)) {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'apim'
        properties: {
          privateDnsZoneId: apimPrivateDnsZoneResourceId
        }
      }
    ]
  }
}

output apimPrincipalId string = apim.identity.principalId
output apimResourceId string = apim.id
output apimGatewayUrl string = 'https://${apim.name}.azure-api.net'
