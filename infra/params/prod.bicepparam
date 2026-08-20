using '../main.bicep'

param environmentProfile = 'prod'
param location = readEnvironmentVariable('AZURE_LOCATION')
param apimName = readEnvironmentVariable('APIM_NAME')
param publisherEmail = readEnvironmentVariable('APIM_PUBLISHER_EMAIL')
param publisherName = readEnvironmentVariable('APIM_PUBLISHER_NAME')
param foundryBaseUrl = readEnvironmentVariable('FOUNDRY_BASE_URL')
param expectedAudience = readEnvironmentVariable('APIM_EXPECTED_AUDIENCE')
param requiredAppRole = readEnvironmentVariable('APIM_REQUIRED_APP_ROLE')

// Required production limits must come from an approved environment capacity record.
param perUserRateLimit = int(readEnvironmentVariable('PER_USER_RATE_LIMIT'))
param perUserHourlyQuota = int(readEnvironmentVariable('PER_USER_HOURLY_QUOTA'))
param perUserTokenLimit = int(readEnvironmentVariable('PER_USER_TOKEN_LIMIT'))
