using '../main.bicep'

param environmentProfile = 'prod'
param location = readEnvironmentVariable('AZURE_LOCATION')
param secondaryLocation = readEnvironmentVariable('AZURE_SECONDARY_LOCATION', '')
param apimName = readEnvironmentVariable('APIM_NAME')
param secondaryApimName = readEnvironmentVariable('APIM_SECONDARY_NAME', '')
param deploySecondary = bool(readEnvironmentVariable('DEPLOY_SECONDARY', 'false'))
param publisherEmail = readEnvironmentVariable('APIM_PUBLISHER_EMAIL')
param publisherName = readEnvironmentVariable('APIM_PUBLISHER_NAME')
param entraTenantId = readEnvironmentVariable('ENTRA_TENANT_ID')
param foundryBaseUrl = readEnvironmentVariable('FOUNDRY_BASE_URL')
param foundrySubscriptionId = readEnvironmentVariable('FOUNDRY_SUBSCRIPTION_ID')
param foundryResourceGroupName = readEnvironmentVariable('FOUNDRY_RESOURCE_GROUP')
param foundryAccountName = readEnvironmentVariable('FOUNDRY_ACCOUNT_NAME')
param expectedAudience = readEnvironmentVariable('APIM_EXPECTED_AUDIENCE')
param requiredAppRole = readEnvironmentVariable('APIM_REQUIRED_APP_ROLE')
param opusDeploymentName = readEnvironmentVariable('ANTHROPIC_DEFAULT_OPUS_MODEL')
param sonnetDeploymentName = readEnvironmentVariable('ANTHROPIC_DEFAULT_SONNET_MODEL')
param haikuDeploymentName = readEnvironmentVariable('ANTHROPIC_DEFAULT_HAIKU_MODEL')

// Required production limits and fixed capacity come from the approved capacity record.
param perUserRateLimit = int(readEnvironmentVariable('PER_USER_RATE_LIMIT'))
param perUserTokenLimit = int(readEnvironmentVariable('PER_USER_TOKEN_LIMIT'))
param apimSkuName = 'PremiumV2'
param defaultCapacity = int(readEnvironmentVariable('APIM_DEFAULT_CAPACITY'))
param autoscaleEnabled = false
param zoneRedundant = true

param networkingProfile = readEnvironmentVariable('APIM_NETWORKING_PROFILE', 'public')
param apimSubnetResourceId = readEnvironmentVariable('APIM_SUBNET_RESOURCE_ID', '')
param secondaryApimSubnetResourceId = readEnvironmentVariable('APIM_SECONDARY_SUBNET_RESOURCE_ID', '')
param existingWorkspaceResourceId = readEnvironmentVariable('LOG_ANALYTICS_WORKSPACE_RESOURCE_ID', '')
param existingAppInsightsResourceId = readEnvironmentVariable('APPLICATION_INSIGHTS_RESOURCE_ID', '')
param actionGroupResourceId = readEnvironmentVariable('ACTION_GROUP_RESOURCE_ID', '')
param trafficManagerEnabled = bool(readEnvironmentVariable('TRAFFIC_MANAGER_ENABLED', 'false'))
param trafficManagerName = readEnvironmentVariable('TRAFFIC_MANAGER_NAME', '${apimName}-failover')
