targetScope = 'resourceGroup'

param apimName string
param location string
param publisherEmail string
param publisherName string
param apimSkuName string
param defaultCapacity int
param zoneRedundant bool
param apimSubnetResourceId string

resource apim 'Microsoft.ApiManagement/service@2024-05-01' = {
  name: apimName
  location: location
  zones: zoneRedundant ? [
    '1'
    '2'
    '3'
  ] : null
  sku: {
    name: apimSkuName
    capacity: defaultCapacity
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
    publicNetworkAccess: 'Disabled'
    virtualNetworkType: 'External'
    virtualNetworkConfiguration: {
      subnetResourceId: apimSubnetResourceId
    }
  }
}
