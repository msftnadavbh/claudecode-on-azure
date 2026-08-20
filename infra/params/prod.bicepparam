using '../main.bicep'

param environmentProfile = 'prod'
param location = 'eastus2'
param apimName = 'apim-claude-prod'
param publisherEmail = 'platform-team@example.com'
param publisherName = 'Platform Engineering'
param foundryHost = 'example-foundry.openai.azure.com'
param expectedAudience = 'api://example-claude-gateway'

// Production placeholders: set by validated capacity model and tenant policy.
param perUserRateLimit = 600
param perUserHourlyQuota = 6000
param perUserTokenLimit = 600000
