targetScope = 'resourceGroup'

@description('Existing Microsoft Foundry account name.')
param foundryAccountName string

@description('APIM managed identity principal ID.')
param principalId string

// Foundry User: documented minimum built-in role for Foundry project data actions.
var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryAccountName
}

resource inferenceRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, principalId, foundryUserRoleId)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
