targetScope = 'resourceGroup'

param enabled bool
param location string
param namePrefix string
param apimInstances array
param existingWorkspaceResourceId string
param existingAppInsightsResourceId string
param autoscaleEnabled bool
param minimumCapacity int
param defaultCapacity int
param maximumCapacity int
param scaleOutCpuThreshold int
param scaleInCpuThreshold int
param memoryAlertThreshold int
param actionGroupResourceId string

var useExistingTelemetry = !empty(existingWorkspaceResourceId) && !empty(existingAppInsightsResourceId)
var telemetryInputsValid = (empty(existingWorkspaceResourceId) && empty(existingAppInsightsResourceId)) || useExistingTelemetry
var validatedExistingWorkspaceResourceId = telemetryInputsValid ? existingWorkspaceResourceId : fail('Provide both existingWorkspaceResourceId and existingAppInsightsResourceId, or neither.')
var appInsightsIdParts = split(existingAppInsightsResourceId, '/')
var existingAppInsightsSubscriptionId = useExistingTelemetry ? appInsightsIdParts[2] : subscription().subscriptionId
var existingAppInsightsResourceGroupName = useExistingTelemetry ? appInsightsIdParts[4] : resourceGroup().name
var existingAppInsightsName = useExistingTelemetry ? last(appInsightsIdParts) : ''
var alertActions = empty(actionGroupResourceId) ? [] : [
  {
    actionGroupId: actionGroupResourceId
  }
]

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (enabled && !useExistingTelemetry) {
  name: '${namePrefix}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = if (enabled && !useExistingTelemetry) {
  name: '${namePrefix}-insights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    DisableIpMasking: false
    IngestionMode: 'LogAnalytics'
  }
}

resource existingAppInsights 'Microsoft.Insights/components@2020-02-02' existing = if (enabled && useExistingTelemetry) {
  name: existingAppInsightsName
  scope: resourceGroup(existingAppInsightsSubscriptionId, existingAppInsightsResourceGroupName)
}

var workspaceResourceId = useExistingTelemetry ? validatedExistingWorkspaceResourceId : workspace.id
var appInsightsConnectionString = useExistingTelemetry ? existingAppInsights!.properties.ConnectionString : appInsights!.properties.ConnectionString

resource apim 'Microsoft.ApiManagement/service@2024-05-01' existing = [for instance in apimInstances: {
  name: instance.name
}]

resource claudeApi 'Microsoft.ApiManagement/service/apis@2024-05-01' existing = [for (instance, i) in apimInstances: {
  parent: apim[i]
  name: 'claude'
}]

resource appInsightsLogger 'Microsoft.ApiManagement/service/loggers@2024-05-01' = [for (instance, i) in apimInstances: if (enabled) {
  parent: apim[i]
  name: 'application-insights'
  properties: {
    loggerType: 'applicationInsights'
    isBuffered: false
    credentials: {
      connectionString: appInsightsConnectionString
      identityClientId: 'SystemAssigned'
    }
  }
}]

module appInsightsPublisherRbac './monitoring-rbac.bicep' = if (enabled) {
  name: 'appInsightsPublisherRbac'
  scope: resourceGroup(existingAppInsightsSubscriptionId, existingAppInsightsResourceGroupName)
  params: {
    appInsightsName: useExistingTelemetry ? existingAppInsightsName : appInsights!.name
    principalIds: map(apimInstances, instance => instance.principalId)
  }
}

resource apiDiagnostic 'Microsoft.ApiManagement/service/apis/diagnostics@2024-05-01' = [for (instance, i) in apimInstances: if (enabled) {
  parent: claudeApi[i]
  name: 'applicationinsights'
  properties: {
    loggerId: appInsightsLogger[i].id
    alwaysLog: 'allErrors'
    logClientIp: false
    sampling: {
      samplingType: 'fixed'
      percentage: 10
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
}]

resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = [for (instance, i) in apimInstances: if (enabled) {
  name: 'send-to-log-analytics'
  scope: apim[i]
  properties: {
    workspaceId: workspaceResourceId
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
}]

resource autoscale 'Microsoft.Insights/autoscalesettings@2022-10-01' = [for (instance, i) in apimInstances: if (autoscaleEnabled) {
  name: '${instance.name}-autoscale'
  location: instance.location
  properties: {
    enabled: true
    targetResourceUri: apim[i].id
    profiles: [
      {
        name: 'cpu-capacity'
        capacity: {
          minimum: string(minimumCapacity)
          default: string(defaultCapacity)
          maximum: string(maximumCapacity)
        }
        rules: [
          {
            metricTrigger: {
              metricName: 'CpuPercent_Gateway'
              metricResourceUri: apim[i].id
              operator: 'GreaterThan'
              statistic: 'Average'
              threshold: scaleOutCpuThreshold
              timeAggregation: 'Average'
              timeGrain: 'PT1M'
              timeWindow: 'PT30M'
            }
            scaleAction: {
              cooldown: 'PT60M'
              direction: 'Increase'
              type: 'ChangeCount'
              value: '1'
            }
          }
          {
            metricTrigger: {
              metricName: 'CpuPercent_Gateway'
              metricResourceUri: apim[i].id
              operator: 'LessThan'
              statistic: 'Average'
              threshold: scaleInCpuThreshold
              timeAggregation: 'Average'
              timeGrain: 'PT1M'
              timeWindow: 'PT30M'
            }
            scaleAction: {
              cooldown: 'PT90M'
              direction: 'Decrease'
              type: 'ChangeCount'
              value: '1'
            }
          }
        ]
      }
    ]
  }
}]

resource capacityAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = [for (instance, i) in apimInstances: if (enabled) {
  name: '${instance.name}-high-capacity'
  location: 'global'
  properties: {
    description: 'APIM gateway CPU capacity is sustained above the scale-out threshold.'
    severity: 2
    enabled: true
    scopes: [
      apim[i].id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighCpu'
          metricName: 'CpuPercent_Gateway'
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
}]

resource memoryAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = [for (instance, i) in apimInstances: if (enabled) {
  name: '${instance.name}-high-memory'
  location: 'global'
  properties: {
    description: 'APIM gateway memory is sustained above the configured threshold.'
    severity: 2
    enabled: true
    scopes: [apim[i].id]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [{
        name: 'HighMemory'
        metricName: 'MemoryPercent_Gateway'
        metricNamespace: 'Microsoft.ApiManagement/service'
        operator: 'GreaterThan'
        threshold: memoryAlertThreshold
        timeAggregation: 'Average'
        criterionType: 'StaticThresholdCriterion'
      }]
    }
    actions: alertActions
  }
}]

resource failureAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = [for (instance, i) in apimInstances: if (enabled) {
  name: '${instance.name}-gateway-errors'
  location: 'global'
  properties: {
    description: 'APIM reports sustained authentication, authorization, or throttling responses.'
    severity: 2
    enabled: true
    scopes: [
      apim[i].id
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
              name: 'GatewayResponseCode'
              operator: 'Include'
              values: [
                '401'
                '403'
                '429'
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
}]

resource gateway5xxAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = [for (instance, i) in apimInstances: if (enabled) {
  name: '${instance.name}-gateway-5xx'
  location: 'global'
  properties: {
    description: 'APIM reports sustained client-visible gateway 5xx responses.'
    severity: 1
    enabled: true
    scopes: [apim[i].id]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [{
        name: 'Gateway5xx'
        metricName: 'Requests'
        metricNamespace: 'Microsoft.ApiManagement/service'
        dimensions: [{
          name: 'GatewayResponseCodeCategory'
          operator: 'Include'
          values: ['5xx']
        }]
        operator: 'GreaterThan'
        threshold: 5
        timeAggregation: 'Total'
        criterionType: 'StaticThresholdCriterion'
      }]
    }
    actions: alertActions
  }
}]

resource backend5xxAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = [for (instance, i) in apimInstances: if (enabled) {
  name: '${instance.name}-backend-5xx'
  location: 'global'
  properties: {
    description: 'Foundry reports sustained backend 5xx responses through APIM.'
    severity: 1
    enabled: true
    scopes: [apim[i].id]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [{
        name: 'Backend5xx'
        metricName: 'Requests'
        metricNamespace: 'Microsoft.ApiManagement/service'
        dimensions: [{
          name: 'BackendResponseCodeCategory'
          operator: 'Include'
          values: ['5xx']
        }]
        operator: 'GreaterThan'
        threshold: 5
        timeAggregation: 'Total'
        criterionType: 'StaticThresholdCriterion'
      }]
    }
    actions: alertActions
  }
}]
