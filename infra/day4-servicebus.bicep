targetScope = 'resourceGroup'

@description('The existing Logic App UAMI name used only to send to the Day 4 queue.')
param logicAppIdentityName string = 'uami-agentic-ai-lab-logicapp'

@description('The existing Function UAMI name used only to receive from the Day 4 queue.')
param functionIdentityName string = 'uami-agentic-ai-lab-storage'

@description('Standard queue name for the integration lab.')
param queueName string = 'integration-events'

@description('Stable unique namespace name derived from this subscription and resource group.')
param namespaceName string = 'sb-ai-int-${uniqueString(resourceGroup().id)}'

@description('Principal/object ID of the existing Logic App UAMI.')
param logicAppPrincipalId string = '9ab0f1a5-7d68-46b6-8431-8e861d9de833'

@description('Principal/object ID of the existing Function UAMI.')
param functionPrincipalId string = '9fadac85-168d-4032-827f-ff98fb8b2410'

@description('Azure Service Bus Data Sender built-in role.')
var serviceBusDataSenderRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39'
)

@description('Azure Service Bus Data Receiver built-in role.')
var serviceBusDataReceiverRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0'
)

resource logicAppIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: logicAppIdentityName
}

resource functionIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: functionIdentityName
}

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: namespaceName
  location: resourceGroup().location
  tags: {
    workload: 'azure-integration-lab'
    sprintDay: '04'
  }
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    minimumTlsVersion: '1.2'
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
    zoneRedundant: false
  }
}

resource queue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  parent: serviceBusNamespace
  name: queueName
  properties: {
    lockDuration: 'PT1M'
    maxDeliveryCount: 5
    deadLetteringOnMessageExpiration: true
    requiresDuplicateDetection: false
    requiresSession: false
    autoDeleteOnIdle: 'P10675199DT2H48M5.4775807S'
    defaultMessageTimeToLive: 'P10675199DT2H48M5.4775807S'
    duplicateDetectionHistoryTimeWindow: 'PT10M'
    enablePartitioning: false
    maxMessageSizeInKilobytes: 256
    maxSizeInMegabytes: 1024
  }
}

resource logicAppSenderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: queue
  name: guid(queue.id, logicAppIdentity.id, serviceBusDataSenderRoleId)
  properties: {
    roleDefinitionId: serviceBusDataSenderRoleId
    principalId: logicAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource functionReceiverAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: queue
  name: guid(queue.id, functionIdentity.id, serviceBusDataReceiverRoleId)
  properties: {
    roleDefinitionId: serviceBusDataReceiverRoleId
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output namespaceName string = serviceBusNamespace.name
output namespaceFqdn string = '${serviceBusNamespace.name}.servicebus.windows.net'
output queueName string = queue.name
output queueResourceId string = queue.id
