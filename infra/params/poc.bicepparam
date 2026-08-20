using '../main.bicep'

param environmentProfile = 'poc'
param location = 'eastus'
param apimName = 'apim-claude-poc'
param publisherEmail = 'platform-team@example.com'
param publisherName = 'Platform Engineering'
param entraTenantId = '00000000-0000-0000-0000-000000000000'
param foundryBaseUrl = 'https://example-foundry.services.ai.azure.com/anthropic'
param foundryResourceGroupName = 'example-foundry-rg'
param foundryAccountName = 'example-foundry'
param expectedAudience = 'api://example-claude-gateway'
param requiredAppRole = 'ClaudeCode.User'
param opusDeploymentName = 'example-claude-deployment'
param sonnetDeploymentName = 'example-claude-deployment'
param haikuDeploymentName = 'example-claude-deployment'

// Intentionally tiny limits for PoC behavior demonstration.
param perUserRateLimit = 20
param perUserHourlyQuota = 40
param perUserTokenLimit = 4000

// Basic v2 is the lowest practical tier supporting Anthropic LLM policies.
param apimSkuName = 'BasicV2'
param minimumCapacity = 1
param defaultCapacity = 1
param maximumCapacity = 1
param autoscaleEnabled = false
param observabilityEnabled = false
