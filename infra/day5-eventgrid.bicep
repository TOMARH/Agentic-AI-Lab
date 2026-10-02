targetScope = 'resourceGroup'

@description('Existing Blob Storage account that publishes BlobCreated events.')
param storageAccountName string = 'saaiazureintegrationlab'

@description('Existing Day 4 Service Bus namespace.')
param serviceBusNamespaceName string = 'sb-ai-int-likwmn7js4ffw'

@description('Existing Day 4 queue.')
param queueName string = 'integration-events'

@description('Event Grid system topic and subscription names.')
param systemTopicName string = 'eg-saaiazureintegrationlab'
param eventSubscriptionName string = 'blob-created-to-day4-queue'

var serviceBusSenderRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39'
)

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2024-01-01' existing = {
  name: serviceBusNamespaceName
}

resource queue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' existing = {
  parent: serviceBusNamespace
  name: queueName
}

resource systemTopic 'Microsoft.EventGrid/systemTopics@2022-06-15' = {
  name: systemTopicName
  location: resourceGroup().location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    source: storageAccount.id
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
  tags: {
    workload: 'azure-integration-lab'
    sprintDay: '05'
  }
}

resource serviceBusSenderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: queue
  name: guid(queue.id, systemTopic.id, serviceBusSenderRoleId)
  properties: {
    roleDefinitionId: serviceBusSenderRoleId
    principalId: systemTopic.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource eventSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2022-06-15' = {
  parent: systemTopic
  name: eventSubscriptionName
  properties: {
    deliveryWithResourceIdentity: {
      identity: {
        type: 'SystemAssigned'
      }
      destination: {
        endpointType: 'ServiceBusQueue'
        properties: {
          resourceId: queue.id
        }
      }
    }
    filter: {
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated'
      ]
      subjectBeginsWith: '/blobServices/default/containers/incoming/blobs/'
      isSubjectCaseSensitive: false
    }
    retryPolicy: {
      maxDeliveryAttempts: 10
      eventTimeToLiveInMinutes: 1440
    }
  }
}

output systemTopicId string = systemTopic.id
output systemTopicPrincipalId string = systemTopic.identity.principalId
output eventSubscriptionId string = eventSubscription.id
output queueResourceId string = queue.id
