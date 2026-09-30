using './day2-function.bicep'

param functionAppName = 'day2fnsprint29'
param functionPlanName = 'ASP-rgaiazureintegrationlab-e2f6'
param location = 'centralindia'
param storageAccountName = 'saaiazureintegrationlab'
param managedIdentityName = 'uami-agentic-ai-lab-storage'
param deploymentContainerName = 'function-deployments'
param applicationInsightsName = 'day2fnsprint29'
param businessContainerName = 'incoming'
param maximumInstanceCount = 1
param instanceMemoryMB = 512
param blobContributorAssignmentName = 'd63de475-998a-4ba1-af28-e3cdd64ff83a'
param blobOwnerAssignmentName = '923a82d2-44c1-4cc7-b7c9-cedea59364b7'
