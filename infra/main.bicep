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

@description('Foundry endpoint hostname, for example myfoundry.openai.azure.com.')
param foundryHost string

@description('Expected Entra audience (Application ID URI or API audience).')
param expectedAudience string

@description('Rate limit calls per minute per user identity.')
param perUserRateLimit int

@description('Quota calls per hour per user identity.')
param perUserHourlyQuota int

@description('Quota tokens per minute per user identity.')
param perUserTokenLimit int

module apim './modules/apim.bicep' = {
  name: 'apimDeployment'
  params: {
    apimName: apimName
    location: location
    publisherEmail: publisherEmail
    publisherName: publisherName
    environmentProfile: environmentProfile
    foundryHost: foundryHost
    expectedAudience: expectedAudience
    perUserRateLimit: perUserRateLimit
    perUserHourlyQuota: perUserHourlyQuota
    perUserTokenLimit: perUserTokenLimit
  }
}
