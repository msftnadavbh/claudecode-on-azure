targetScope = 'resourceGroup'

@allowed([
  'poc'
  'prod'
])
param environmentProfile string

@description('Azure region for APIM.')
param location string = resourceGroup().location

@description('APIM service name.')
param apimName string

@description('Publisher email for APIM.')
param publisherEmail string

@description('Publisher name for APIM.')
param publisherName string

@description('Foundry Anthropic base URL copied from Foundry, including the /anthropic path.')
param foundryBaseUrl string

@description('Expected Entra audience (Application ID URI or API audience).')
param expectedAudience string

@description('Entra app role required to invoke the gateway.')
param requiredAppRole string

@description('Rate limit calls per minute per user identity.')
@minValue(1)
param perUserRateLimit int

@description('Quota calls per hour per user identity.')
@minValue(1)
param perUserHourlyQuota int

@description('Quota tokens per minute per user identity.')
@minValue(1)
param perUserTokenLimit int

module apim './modules/apim.bicep' = {
  name: 'apimDeployment'
  params: {
    apimName: apimName
    location: location
    publisherEmail: publisherEmail
    publisherName: publisherName
    environmentProfile: environmentProfile
    foundryBaseUrl: foundryBaseUrl
    expectedAudience: expectedAudience
    requiredAppRole: requiredAppRole
    perUserRateLimit: perUserRateLimit
    perUserHourlyQuota: perUserHourlyQuota
    perUserTokenLimit: perUserTokenLimit
  }
}
