using '../main.bicep'

param environmentProfile = 'poc'
param location = 'eastus'
param apimName = 'apim-claude-poc'
param publisherEmail = 'platform-team@example.com'
param publisherName = 'Platform Engineering'
param foundryBaseUrl = 'https://example-foundry.services.ai.azure.com/anthropic'
param expectedAudience = 'api://example-claude-gateway'
param requiredAppRole = 'ClaudeCode.User'

// Intentionally tiny limits for PoC behavior demonstration.
param perUserRateLimit = 20
param perUserHourlyQuota = 40
param perUserTokenLimit = 4000
