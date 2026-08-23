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

@description('Allow Claude Desktop delegated access as an alternative to the existing app role.')
param enableClaudeDesktopDelegatedAuth bool = false

@description('Public client ID used by managed Claude Desktop.')
param claudeDesktopClientId string = 'disabled'

@description('Delegated scope claim required from managed Claude Desktop.')
param claudeDesktopDelegatedScope string = 'disabled'

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

@description('Quota tokens per minute per user identity.')
@minValue(1)
param perUserTokenLimit int

@minValue(1)
@maxValue(2000)
@description('Maximum concurrent forwarded requests per user identity.')
param perUserConcurrentStreamLimit int = 2000

@minValue(1)
@maxValue(2000)
@description('Maximum concurrent forwarded requests to one Foundry authority.')
param aggregateConcurrentStreamLimit int = 2000

@allowed(['BasicV2', 'StandardV2', 'PremiumV2'])
@description('APIM v2 SKU. Production private and zone-redundant profiles require PremiumV2.')
param apimSkuName string

@minValue(1)
@description('Initially deployed APIM capacity.')
param defaultCapacity int

@minValue(1)
@description('Minimum warm APIM capacity.')
param minimumCapacity int = defaultCapacity

@minValue(1)
@description('Maximum autoscale APIM capacity.')
param maximumCapacity int = defaultCapacity

@description('Enable Azure Monitor autoscale for production APIM instances.')
param autoscaleEnabled bool = false

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

@description('Existing dedicated subnet resource ID for Premium v2 VNet injection.')
param apimSubnetResourceId string = ''

@description('Existing dedicated subnet resource ID for secondary Premium v2 VNet injection.')
param secondaryApimSubnetResourceId string = ''

@description('Deploy Log Analytics, Application Insights, APIM diagnostics, and alerts.')
param observabilityEnabled bool = true

@description('Existing shared Log Analytics workspace resource ID. Leave both telemetry IDs empty to create shared resources.')
param existingWorkspaceResourceId string = ''

@description('Existing shared Application Insights resource ID. Leave both telemetry IDs empty to create shared resources.')
param existingAppInsightsResourceId string = ''

@description('Resource ID of an existing Action Group. Empty creates alerts without actions.')
param actionGroupResourceId string = ''

@minValue(1)
@maxValue(100)
param memoryAlertThreshold int = 80

@description('Deploy Traffic Manager priority routing for public secondary APIM.')
param trafficManagerEnabled bool = deploySecondary && networkingProfile == 'public'

@description('Globally unique Traffic Manager profile name.')
param trafficManagerName string = '${apimName}-failover'

var foundryBaseUri = parseUri(foundryBaseUrl)
var secondaryFoundryBaseUri = deploySecondary ? parseUri(secondaryFoundryBaseUrl) : foundryBaseUri
var foundryBaseUrlIsValid = foundryBaseUri.scheme == 'https' && endsWith(toLower(foundryBaseUri.host), '.services.ai.azure.com') && foundryBaseUri.path == '/anthropic' && toLower(foundryBaseUrl) == 'https://${toLower(foundryBaseUri.host)}/anthropic'
var secondaryFoundryBaseUrlIsValid = !deploySecondary || (secondaryFoundryBaseUri.scheme == 'https' && endsWith(toLower(secondaryFoundryBaseUri.host), '.services.ai.azure.com') && secondaryFoundryBaseUri.path == '/anthropic' && toLower(secondaryFoundryBaseUrl) == 'https://${toLower(secondaryFoundryBaseUri.host)}/anthropic')
var validatedFoundryBaseUrl = foundryBaseUrlIsValid ? foundryBaseUrl : fail('Foundry base URL must use an HTTPS *.services.ai.azure.com host and exactly the /anthropic path, without additional URI components.')
var validatedSecondaryFoundryBaseUrl = secondaryFoundryBaseUrlIsValid ? secondaryFoundryBaseUrl : fail('Secondary Foundry base URL must use an HTTPS *.services.ai.azure.com host and exactly the /anthropic path, without additional URI components.')
var validatedSecondaryLocation = !deploySecondary || !empty(secondaryLocation) ? secondaryLocation : fail('secondaryLocation is required when deploySecondary is true.')
var validatedSecondaryApimName = !deploySecondary || !empty(secondaryApimName) ? secondaryApimName : fail('secondaryApimName is required when deploySecondary is true.')
var validatedApimSubnetResourceId = networkingProfile != 'private' || !empty(apimSubnetResourceId) ? apimSubnetResourceId : fail('Private networking requires the primary APIM integration subnet.')
var validatedSecondaryApimSubnetResourceId = networkingProfile != 'private' || !deploySecondary || !empty(secondaryApimSubnetResourceId) ? secondaryApimSubnetResourceId : fail('Private networking requires the secondary APIM integration subnet.')
var deployTrafficManager = deploySecondary && trafficManagerEnabled && networkingProfile == 'public'
var validatedActionGroupResourceId = environmentProfile != 'prod' || !empty(actionGroupResourceId) ? actionGroupResourceId : fail('Production requires an existing Action Group resource ID.')

module primaryApim './modules/apim.bicep' = {
  name: 'primaryApim'
  params: {
    apimName: apimName
    location: location
    foundryBaseUrl: validatedFoundryBaseUrl
    environmentProfile: environmentProfile
    publisherEmail: publisherEmail
    publisherName: publisherName
    entraTenantId: entraTenantId
    expectedAudience: expectedAudience
    requiredAppRole: requiredAppRole
    enableClaudeDesktopDelegatedAuth: enableClaudeDesktopDelegatedAuth
    claudeDesktopClientId: claudeDesktopClientId
    claudeDesktopDelegatedScope: claudeDesktopDelegatedScope
    perUserRateLimit: perUserRateLimit
    perUserTokenLimit: perUserTokenLimit
    perUserConcurrentStreamLimit: perUserConcurrentStreamLimit
    aggregateConcurrentStreamLimit: aggregateConcurrentStreamLimit
    apimSkuName: apimSkuName
    minimumCapacity: minimumCapacity
    defaultCapacity: defaultCapacity
    maximumCapacity: maximumCapacity
    zoneRedundant: zoneRedundant
    networkingProfile: networkingProfile
    apimSubnetResourceId: validatedApimSubnetResourceId
  }
}

module secondaryApim './modules/apim.bicep' = if (deploySecondary) {
  name: 'secondaryApim'
  params: {
    apimName: validatedSecondaryApimName
    location: validatedSecondaryLocation
    foundryBaseUrl: validatedSecondaryFoundryBaseUrl
    environmentProfile: environmentProfile
    publisherEmail: publisherEmail
    publisherName: publisherName
    entraTenantId: entraTenantId
    expectedAudience: expectedAudience
    requiredAppRole: requiredAppRole
    enableClaudeDesktopDelegatedAuth: enableClaudeDesktopDelegatedAuth
    claudeDesktopClientId: claudeDesktopClientId
    claudeDesktopDelegatedScope: claudeDesktopDelegatedScope
    perUserRateLimit: perUserRateLimit
    perUserTokenLimit: perUserTokenLimit
    perUserConcurrentStreamLimit: perUserConcurrentStreamLimit
    aggregateConcurrentStreamLimit: aggregateConcurrentStreamLimit
    apimSkuName: apimSkuName
    minimumCapacity: minimumCapacity
    defaultCapacity: defaultCapacity
    maximumCapacity: maximumCapacity
    zoneRedundant: zoneRedundant
    networkingProfile: networkingProfile
    apimSubnetResourceId: validatedSecondaryApimSubnetResourceId
  }
}

var apimInstances = concat([
  {
    name: apimName
    location: location
    principalId: primaryApim.outputs.apimPrincipalId
  }
], deploySecondary ? [
  {
    name: validatedSecondaryApimName
    location: validatedSecondaryLocation
    principalId: secondaryApim!.outputs.apimPrincipalId
  }
] : [])

module observability './modules/observability.bicep' = {
  name: 'sharedObservability'
  params: {
    enabled: observabilityEnabled
    location: location
    namePrefix: apimName
    apimInstances: apimInstances
    existingWorkspaceResourceId: existingWorkspaceResourceId
    existingAppInsightsResourceId: existingAppInsightsResourceId
    autoscaleEnabled: autoscaleEnabled
    minimumCapacity: minimumCapacity
    defaultCapacity: defaultCapacity
    maximumCapacity: maximumCapacity
    scaleOutCpuThreshold: scaleOutCpuThreshold
    scaleInCpuThreshold: scaleInCpuThreshold
    memoryAlertThreshold: memoryAlertThreshold
    actionGroupResourceId: validatedActionGroupResourceId
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

resource trafficManager 'Microsoft.Network/trafficManagerProfiles@2022-04-01' = if (deployTrafficManager) {
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

resource primaryTrafficEndpoint 'Microsoft.Network/trafficManagerProfiles/externalEndpoints@2022-04-01' = if (deployTrafficManager) {
  parent: trafficManager
  name: 'primary'
  properties: {
    endpointStatus: 'Enabled'
    target: primaryApim.outputs.apimGatewayHostname
    priority: 1
  }
}

resource secondaryTrafficEndpoint 'Microsoft.Network/trafficManagerProfiles/externalEndpoints@2022-04-01' = if (deployTrafficManager) {
  parent: trafficManager
  name: 'secondary'
  properties: {
    endpointStatus: 'Enabled'
    target: secondaryApim!.outputs.apimGatewayHostname
    priority: 2
  }
}

output primaryGatewayUrl string = primaryApim.outputs.apimGatewayUrl
output secondaryGatewayUrl string = deploySecondary ? secondaryApim!.outputs.apimGatewayUrl : ''
output gatewayFailoverFqdn string = deployTrafficManager ? trafficManager!.properties.dnsConfig.fqdn : ''
output opusModel string = opusDeploymentName
output sonnetModel string = sonnetDeploymentName
output haikuModel string = haikuDeploymentName
