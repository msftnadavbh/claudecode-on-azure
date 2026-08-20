targetScope = 'resourceGroup'

@allowed(['poc', 'prod'])
param environmentProfile string

@description('Primary Azure region.')
param location string = resourceGroup().location

@description('Secondary Azure region. Required when deploySecondary is true.')
param secondaryLocation string = ''

@description('Primary APIM service name.')
@minLength(1)
param apimName string

@description('Secondary APIM service name.')
param secondaryApimName string = ''

@description('Deploy an independent secondary APIM failure domain.')
param deploySecondary bool = false

@description('Publisher email for APIM.')
@minLength(3)
param publisherEmail string

@description('Publisher name for APIM.')
@minLength(1)
param publisherName string

@description('Microsoft Entra tenant ID that issues caller tokens.')
@minLength(36)
@maxLength(36)
param entraTenantId string

@description('Expected Entra audience (Application ID URI or API audience).')
@minLength(1)
param expectedAudience string

@description('Entra app role required to invoke the gateway.')
@minLength(1)
param requiredAppRole string

@description('Primary Foundry Anthropic base URL copied from Foundry, including /anthropic.')
@minLength(1)
param foundryBaseUrl string

@description('Secondary Foundry Anthropic base URL. Defaults to the primary endpoint.')
param secondaryFoundryBaseUrl string = foundryBaseUrl

@description('Subscription containing the existing Foundry account.')
param foundrySubscriptionId string = subscription().subscriptionId

@description('Resource group containing the existing primary Foundry account.')
@minLength(1)
param foundryResourceGroupName string

@description('Existing primary Foundry account name. The template only assigns inference RBAC.')
@minLength(1)
param foundryAccountName string

@description('Existing secondary Foundry account name. Defaults to the primary account.')
param secondaryFoundryAccountName string = foundryAccountName

@description('Existing secondary Foundry account resource group. Defaults to the primary resource group.')
param secondaryFoundryResourceGroupName string = foundryResourceGroupName

@description('Foundry deployment name pinned for the Opus role.')
@minLength(1)
param opusDeploymentName string

@description('Foundry deployment name pinned for the Sonnet role.')
@minLength(1)
param sonnetDeploymentName string

@description('Foundry deployment name pinned for the Haiku role.')
@minLength(1)
param haikuDeploymentName string

@description('Rate limit calls per minute per user identity.')
@minValue(1)
param perUserRateLimit int

@description('Quota calls per hour per user identity.')
@minValue(1)
param perUserHourlyQuota int

@description('Quota tokens per minute per user identity.')
@minValue(1)
param perUserTokenLimit int

@allowed(['BasicV2', 'StandardV2', 'PremiumV2'])
@description('APIM v2 SKU. Production private and zone-redundant profiles require PremiumV2.')
param apimSkuName string

@minValue(1)
@description('Minimum warm APIM capacity.')
param minimumCapacity int

@minValue(1)
@description('Initially deployed APIM capacity.')
param defaultCapacity int

@minValue(1)
@description('Maximum autoscale APIM capacity.')
param maximumCapacity int

@description('Enable Azure Monitor autoscale for production APIM instances.')
param autoscaleEnabled bool

@minValue(1)
@maxValue(100)
param scaleOutCpuThreshold int = 70

@minValue(1)
@maxValue(100)
param scaleInCpuThreshold int = 30

@description('Enable Premium v2 availability-zone redundancy at creation.')
param zoneRedundant bool = false

@allowed(['public', 'private'])
@description('Gateway networking profile.')
param networkingProfile string = 'public'

@description('Existing delegated subnet resource ID for Premium v2 outbound VNet integration.')
param apimSubnetResourceId string = ''

@description('Existing subnet resource ID for the primary APIM private endpoint.')
param apimPrivateEndpointSubnetResourceId string = ''

@description('Existing delegated subnet resource ID for secondary APIM outbound VNet integration.')
param secondaryApimSubnetResourceId string = ''

@description('Existing subnet resource ID for the secondary APIM private endpoint.')
param secondaryApimPrivateEndpointSubnetResourceId string = ''

@description('Existing private DNS zone resource ID for privatelink.azure-api.net.')
param apimPrivateDnsZoneResourceId string = ''

@description('Deploy Log Analytics, Application Insights, APIM diagnostics, and alerts.')
param observabilityEnabled bool = true

@description('Resource ID of an existing Action Group. Empty creates alerts without actions.')
param actionGroupResourceId string = ''

@description('Deploy Traffic Manager priority routing when secondary APIM is enabled.')
param trafficManagerEnabled bool = deploySecondary

@description('Globally unique Traffic Manager profile name.')
param trafficManagerName string = '${apimName}-failover'

module primaryApim './modules/apim.bicep' = {
  name: 'primaryApim'
  params: {
    apimName: apimName
    location: location
    foundryBaseUrl: foundryBaseUrl
    environmentProfile: environmentProfile
    publisherEmail: publisherEmail
    publisherName: publisherName
    entraTenantId: entraTenantId
    expectedAudience: expectedAudience
    requiredAppRole: requiredAppRole
    perUserRateLimit: perUserRateLimit
    perUserHourlyQuota: perUserHourlyQuota
    perUserTokenLimit: perUserTokenLimit
    apimSkuName: apimSkuName
    minimumCapacity: minimumCapacity
    defaultCapacity: defaultCapacity
    maximumCapacity: maximumCapacity
    autoscaleEnabled: autoscaleEnabled
    scaleOutCpuThreshold: scaleOutCpuThreshold
    scaleInCpuThreshold: scaleInCpuThreshold
    zoneRedundant: zoneRedundant
    networkingProfile: networkingProfile
    apimSubnetResourceId: apimSubnetResourceId
    apimPrivateEndpointSubnetResourceId: apimPrivateEndpointSubnetResourceId
    apimPrivateDnsZoneResourceId: apimPrivateDnsZoneResourceId
    observabilityEnabled: observabilityEnabled
    actionGroupResourceId: actionGroupResourceId
  }
}

module secondaryApim './modules/apim.bicep' = if (deploySecondary) {
  name: 'secondaryApim'
  params: {
    apimName: secondaryApimName
    location: secondaryLocation
    foundryBaseUrl: secondaryFoundryBaseUrl
    environmentProfile: environmentProfile
    publisherEmail: publisherEmail
    publisherName: publisherName
    entraTenantId: entraTenantId
    expectedAudience: expectedAudience
    requiredAppRole: requiredAppRole
    perUserRateLimit: perUserRateLimit
    perUserHourlyQuota: perUserHourlyQuota
    perUserTokenLimit: perUserTokenLimit
    apimSkuName: apimSkuName
    minimumCapacity: minimumCapacity
    defaultCapacity: defaultCapacity
    maximumCapacity: maximumCapacity
    autoscaleEnabled: autoscaleEnabled
    scaleOutCpuThreshold: scaleOutCpuThreshold
    scaleInCpuThreshold: scaleInCpuThreshold
    zoneRedundant: zoneRedundant
    networkingProfile: networkingProfile
    apimSubnetResourceId: secondaryApimSubnetResourceId
    apimPrivateEndpointSubnetResourceId: secondaryApimPrivateEndpointSubnetResourceId
    apimPrivateDnsZoneResourceId: apimPrivateDnsZoneResourceId
    observabilityEnabled: observabilityEnabled
    actionGroupResourceId: actionGroupResourceId
  }
}

module primaryFoundryRbac './modules/foundry-rbac.bicep' = {
  name: 'primaryFoundryInferenceRbac'
  scope: resourceGroup(foundrySubscriptionId, foundryResourceGroupName)
  params: {
    foundryAccountName: foundryAccountName
    principalId: primaryApim.outputs.apimPrincipalId
  }
}

module secondaryFoundryRbac './modules/foundry-rbac.bicep' = if (deploySecondary) {
  name: 'secondaryFoundryInferenceRbac'
  scope: resourceGroup(foundrySubscriptionId, secondaryFoundryResourceGroupName)
  params: {
    foundryAccountName: secondaryFoundryAccountName
    principalId: secondaryApim!.outputs.apimPrincipalId
  }
}

resource trafficManager 'Microsoft.Network/trafficManagerProfiles@2022-04-01' = if (deploySecondary && trafficManagerEnabled) {
  name: trafficManagerName
  location: 'global'
  properties: {
    profileStatus: 'Enabled'
    trafficRoutingMethod: 'Priority'
    dnsConfig: {
      relativeName: trafficManagerName
      ttl: 30
    }
    monitorConfig: {
      protocol: 'HTTPS'
      port: 443
      path: '/claude/health'
      intervalInSeconds: 30
      timeoutInSeconds: 10
      toleratedNumberOfFailures: 3
    }
  }
}

resource primaryTrafficEndpoint 'Microsoft.Network/trafficManagerProfiles/azureEndpoints@2022-04-01' = if (deploySecondary && trafficManagerEnabled) {
  parent: trafficManager
  name: 'primary'
  properties: {
    endpointStatus: 'Enabled'
    endpointMonitorStatus: 'CheckingEndpoint'
    targetResourceId: primaryApim.outputs.apimResourceId
    priority: 1
  }
}

resource secondaryTrafficEndpoint 'Microsoft.Network/trafficManagerProfiles/azureEndpoints@2022-04-01' = if (deploySecondary && trafficManagerEnabled) {
  parent: trafficManager
  name: 'secondary'
  properties: {
    endpointStatus: 'Enabled'
    endpointMonitorStatus: 'CheckingEndpoint'
    targetResourceId: secondaryApim!.outputs.apimResourceId
    priority: 2
  }
}

output primaryGatewayUrl string = primaryApim.outputs.apimGatewayUrl
output secondaryGatewayUrl string = deploySecondary ? secondaryApim!.outputs.apimGatewayUrl : ''
output gatewayFailoverFqdn string = deploySecondary && trafficManagerEnabled ? trafficManager!.properties.dnsConfig.fqdn : ''
output opusModel string = opusDeploymentName
output sonnetModel string = sonnetDeploymentName
output haikuModel string = haikuDeploymentName
