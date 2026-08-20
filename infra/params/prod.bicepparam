using '../main.bicep'

param environmentProfile = 'prod'
param location = readEnvironmentVariable('AZURE_LOCATION')
param secondaryLocation = readEnvironmentVariable('AZURE_SECONDARY_LOCATION')
param apimName = readEnvironmentVariable('APIM_NAME')
param secondaryApimName = readEnvironmentVariable('APIM_SECONDARY_NAME')
param deploySecondary = true
param publisherEmail = readEnvironmentVariable('APIM_PUBLISHER_EMAIL')
param publisherName = readEnvironmentVariable('APIM_PUBLISHER_NAME')
param entraTenantId = readEnvironmentVariable('ENTRA_TENANT_ID')
param foundryBaseUrl = readEnvironmentVariable('FOUNDRY_BASE_URL')
param secondaryFoundryBaseUrl = readEnvironmentVariable('FOUNDRY_SECONDARY_BASE_URL')
param foundrySubscriptionId = readEnvironmentVariable('FOUNDRY_SUBSCRIPTION_ID')
param foundryResourceGroupName = readEnvironmentVariable('FOUNDRY_RESOURCE_GROUP')
param foundryAccountName = readEnvironmentVariable('FOUNDRY_ACCOUNT_NAME')
param secondaryFoundryResourceGroupName = readEnvironmentVariable('FOUNDRY_SECONDARY_RESOURCE_GROUP')
param secondaryFoundryAccountName = readEnvironmentVariable('FOUNDRY_SECONDARY_ACCOUNT_NAME')
param expectedAudience = readEnvironmentVariable('APIM_EXPECTED_AUDIENCE')
param requiredAppRole = readEnvironmentVariable('APIM_REQUIRED_APP_ROLE')
param opusDeploymentName = readEnvironmentVariable('ANTHROPIC_DEFAULT_OPUS_MODEL')
param sonnetDeploymentName = readEnvironmentVariable('ANTHROPIC_DEFAULT_SONNET_MODEL')
param haikuDeploymentName = readEnvironmentVariable('ANTHROPIC_DEFAULT_HAIKU_MODEL')

// Required production limits and capacity come from the approved capacity record.
param perUserRateLimit = int(readEnvironmentVariable('PER_USER_RATE_LIMIT'))
param perUserHourlyQuota = int(readEnvironmentVariable('PER_USER_HOURLY_QUOTA'))
param perUserTokenLimit = int(readEnvironmentVariable('PER_USER_TOKEN_LIMIT'))
param apimSkuName = 'PremiumV2'
param minimumCapacity = int(readEnvironmentVariable('APIM_MIN_CAPACITY'))
param defaultCapacity = int(readEnvironmentVariable('APIM_DEFAULT_CAPACITY'))
param maximumCapacity = int(readEnvironmentVariable('APIM_MAX_CAPACITY'))
param autoscaleEnabled = true
param scaleOutCpuThreshold = int(readEnvironmentVariable('APIM_SCALE_OUT_CPU_THRESHOLD'))
param scaleInCpuThreshold = int(readEnvironmentVariable('APIM_SCALE_IN_CPU_THRESHOLD'))
param zoneRedundant = true

param networkingProfile = readEnvironmentVariable('APIM_NETWORKING_PROFILE')
param apimSubnetResourceId = readEnvironmentVariable('APIM_SUBNET_RESOURCE_ID')
param apimPrivateEndpointSubnetResourceId = readEnvironmentVariable('APIM_PRIVATE_ENDPOINT_SUBNET_RESOURCE_ID')
param secondaryApimSubnetResourceId = readEnvironmentVariable('APIM_SECONDARY_SUBNET_RESOURCE_ID')
param secondaryApimPrivateEndpointSubnetResourceId = readEnvironmentVariable('APIM_SECONDARY_PRIVATE_ENDPOINT_SUBNET_RESOURCE_ID')
param apimPrivateDnsZoneResourceId = readEnvironmentVariable('APIM_PRIVATE_DNS_ZONE_RESOURCE_ID')
param actionGroupResourceId = readEnvironmentVariable('ACTION_GROUP_RESOURCE_ID')
param trafficManagerName = readEnvironmentVariable('TRAFFIC_MANAGER_NAME')
