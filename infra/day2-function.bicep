targetScope = 'resourceGroup'

@description('Name of the existing Flex Consumption Function App.')
param functionAppName string = 'day2fnsprint29'

@description('Name of the existing Flex Consumption plan.')
param functionPlanName string = 'ASP-rgaiazureintegrationlab-e2f6'

@description('Azure region for the Function App and plan.')
param location string = resourceGroup().location

@description('Name of the existing business and host storage account.')
param storageAccountName string = 'saaiazureintegrationlab'

@description('Name of the existing user-assigned managed identity.')
param managedIdentityName string = 'uami-agentic-ai-lab-storage'

@description('Private Blob container used by Flex for deployment packages.')
param deploymentContainerName string = 'function-deployments'

@description('Existing Application Insights component created with the Function App.')
param applicationInsightsName string = 'day2fnsprint29'

@description('Business Blob container listed by the HTTP Function.')
param businessContainerName string = 'incoming'

@description('Maximum on-demand instance count. One is a lab cost cap, not a production availability target.')
@minValue(1)
@maxValue(1000)
param maximumInstanceCount int = 1

@description('Flex Consumption instance memory in MB.')
@allowed([512, 2048, 4096])
param instanceMemoryMB int = 512

@description('Current name of the existing Blob Data Contributor assignment; retaining it prevents a duplicate assignment.')
param blobContributorAssignmentName string = 'd63de475-998a-4ba1-af28-e3cdd64ff83a'

@description('Current name of the Blob Data Owner assignment added for Functions host storage.')
param blobOwnerAssignmentName string = '923a82d2-44c1-4cc7-b7c9-cedea59364b7'

var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)
var storageBlobDataOwnerRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
)

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' existing = {
  parent: storage
  name: 'default'
}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: managedIdentityName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  parent: blobService
  name: deploymentContainerName
}

resource flexPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: functionPlanName
  location: location
  kind: 'functionapp'
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  tags: {
  'hidden-link: /app-insights-resource-id': applicationInsights.id
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    serverFarmId: flexPlan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}${deploymentContainer.name}'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: managedIdentity.id
          }
        }
      }
      runtime: {
        name: 'python'
        version: '3.14'
      }
      scaleAndConcurrency: {
        maximumInstanceCount: maximumInstanceCount
        instanceMemoryMB: instanceMemoryMB
      }
    }
  }
}

resource functionAppSettings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: functionApp
  name: 'appsettings'
  properties: {
    AzureWebJobsStorage__accountName: storage.name
    AzureWebJobsStorage__credential: 'managedidentity'
    AzureWebJobsStorage__clientId: managedIdentity.properties.clientId
    AZURE_CLIENT_ID: managedIdentity.properties.clientId
    BLOB_STORAGE_ACCOUNT_URL: storage.properties.primaryEndpoints.blob
    BLOB_CONTAINER_NAME: businessContainerName
    APPLICATIONINSIGHTS_CONNECTION_STRING: applicationInsights.properties.ConnectionString
  }
}

resource blobContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: blobContributorAssignmentName
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleId
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource blobOwnerAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: blobOwnerAssignmentName
  properties: {
    roleDefinitionId: storageBlobDataOwnerRoleId
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output functionAppResourceId string = functionApp.id
output functionAppHostname string = functionApp.properties.defaultHostName
output flexPlanSku string = flexPlan.sku.name
