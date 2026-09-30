# Azure Integration Sprint — Day 2 deployment record

**Completed:** 30 September 2026 (Asia/Kolkata)
**Status:** Deployed and verified; changes remain uncommitted and unpushed.

## Result

The existing Python v2 Function project was deployed to Azure Functions Flex Consumption. The deployed endpoint authenticated with its preserved `FUNCTION` authorization level, then listed the existing `incoming` container using the existing user-assigned managed identity (UAMI). No storage key or storage connection string was used by the Function.

```text
HTTP 200
Container 'incoming' contains 0 blob(s):
```

An empty container is a successful result here: the host indexed and ran the Function, the function key was accepted, the UAMI obtained an Entra token, and Blob Storage authorized the list operation.

## Resources

| Resource | Name | Details |
|---|---|---|
| Resource group | `rg-ai-azure-integration-lab` | Existing; Central India |
| Function App | `day2fnsprint29` | `https://day2fnsprint29.azurewebsites.net` |
| Hosting plan | `ASP-rgaiazureintegrationlab-e2f6` | Flex Consumption, SKU `FC1`, Linux, Central India |
| Runtime | Python 3.14 | Functions runtime v4 |
| Existing business storage | `saaiazureintegrationlab` | StorageV2, Standard LRS, Central India; `incoming` and `processed` already existed |
| Deployment container | `function-deployments` | Private container in `saaiazureintegrationlab` |
| Existing UAMI | `uami-agentic-ai-lab-storage` | Client ID `d45e36bc-698a-4cf2-9943-96eea26bd4d4`; principal ID `9fadac85-168d-4032-827f-ff98fb8b2410` |
| Application Insights | `day2fnsprint29` | Created with the Function App for monitoring |

No duplicate storage account or managed identity was created. The app uses the existing storage account in two logically distinct ways: `AzureWebJobsStorage__*` configures Functions host storage, while `BLOB_STORAGE_ACCOUNT_URL` configures the application’s business Blob client. Flex deployment packages are stored in the separate `function-deployments` container of that same account. This keeps the settings and purpose distinct while reusing the account as requested.

## Identity and role assignments

The same UAMI is attached to the Function App and used for the Flex deployment package container, Functions host storage, and the business Blob SDK.

| Role | Scope | State / purpose |
|---|---|---|
| Storage Blob Data Contributor | `/subscriptions/e5939949-6509-48de-964b-5f1b65c34714/resourceGroups/rg-ai-azure-integration-lab/providers/Microsoft.Storage/storageAccounts/saaiazureintegrationlab` | Existing assignment reused for deployment package access and business Blob access |
| Storage Blob Data Owner | Same storage-account scope | Added for the Functions host’s minimum `AzureWebJobsStorage` permissions |

The existing Blob Data Contributor assignment was already at account scope. Because the host and business data use the same account, the new host role is also at account scope and applies across that account’s blob data. This is broader than a dedicated host account would be, but avoids creating a second account and honors the sprint constraint. No additional queue or table role was added because this app currently has only an HTTP trigger and no queue, table, timer, Blob-trigger, or Durable Functions binding. Storage Table Data Contributor can be added later if host diagnostic-event persistence is needed.

### Host storage and business Blob settings

The Function App uses these host settings, with no plain `AzureWebJobsStorage` connection-string setting:

```text
AzureWebJobsStorage__accountName=saaiazureintegrationlab
AzureWebJobsStorage__credential=managedidentity
AzureWebJobsStorage__clientId=d45e36bc-698a-4cf2-9943-96eea26bd4d4
```

The business SDK settings are:

```text
BLOB_STORAGE_ACCOUNT_URL=https://saaiazureintegrationlab.blob.core.windows.net/
BLOB_CONTAINER_NAME=incoming
AZURE_CLIENT_ID=d45e36bc-698a-4cf2-9943-96eea26bd4d4
```

`AZURE_CLIENT_ID` selects the existing UAMI for the Python `DefaultAzureCredential` chain. The host connection separately names that same UAMI through its connection-specific `AzureWebJobsStorage__clientId` setting. The app’s settings were checked: a plain `AzureWebJobsStorage` setting is absent. The platform-created `APPLICATIONINSIGHTS_CONNECTION_STRING` is for telemetry, not Storage authentication.

## Deployment settings and cost choices

- Flex Consumption was selected because Microsoft recommends it for new serverless Functions and it supports managed-identity host storage without Azure Files.
- Instance memory is **512 MB**, the smallest Flex size, appropriate for this small HTTP/SDK demonstration.
- Maximum on-demand instances is **1** to cap this lab’s scale-out. This is a lab limit, not a production availability recommendation.
- Always-ready instances are **0** (`alwaysReady: []`), so there is no always-ready baseline charge and the app can scale to zero.
- Application Insights was enabled for runtime and exception visibility. Its ingestion and retention are usage-based; monitor actual volume and the current Azure Monitor terms.
- The existing StorageV2 account’s `allowSharedKeyAccess` setting is `true`; it was left unchanged for other existing users. This Function’s host and SDK storage connections use managed identity, not shared keys.

Flex Consumption bills on-demand executions by execution count and memory-time. Current Microsoft pricing lists a monthly on-demand grant of 250,000 executions and 100,000 GB-seconds per subscription for eligible pay-as-you-go subscriptions; the grant is shared across Function Apps in that subscription. Storage, transactions, networking, and monitoring are separate meters, so the existing account and Application Insights can still incur charges. No fixed monthly price is claimed here because the subscription offer, region, and usage determine the bill.

## Commands and operations

### Confirm the target and current prerequisites

```powershell
az account show --query '{name:name,id:id,tenantId:tenantId,user:user.name}' -o json
az identity show --name uami-agentic-ai-lab-storage --resource-group rg-ai-azure-integration-lab --query '{id:id,clientId:clientId,principalId:principalId}' -o json
az storage account show --name saaiazureintegrationlab --resource-group rg-ai-azure-integration-lab --query '{id:id,location:location,sku:sku.name,kind:kind,allowSharedKeyAccess:allowSharedKeyAccess,blob:primaryEndpoints.blob,queue:primaryEndpoints.queue,table:primaryEndpoints.table}' -o json
az functionapp list-runtimes --os linux
```

The active subscription was `e5939949-6509-48de-964b-5f1b65c34714`, tenant `70a887c3-533b-4cdb-89a3-4ed571acb2a0`. The existing account was confirmed as `StorageV2`, Standard LRS, with Blob, Queue, and Table endpoints. Azure listed Python 3.14 as a supported Linux Functions runtime.

### Register the Functions resource provider

The first create attempt was rejected before creating an app because `Microsoft.Web` was not registered. Its state was checked, then it was registered:

```powershell
az provider show --namespace Microsoft.Web --query '{namespace:namespace,state:registrationState}' -o json
az provider register --namespace Microsoft.Web --wait
```

Azure also registered `Microsoft.OperationalInsights` and `Microsoft.Insights` during Function App creation for the enabled monitoring resource.

### Grant host storage access and create the private deployment container

```powershell
az role assignment create --assignee-object-id 9fadac85-168d-4032-827f-ff98fb8b2410 --assignee-principal-type ServicePrincipal --role 'Storage Blob Data Owner' --scope '/subscriptions/e5939949-6509-48de-964b-5f1b65c34714/resourceGroups/rg-ai-azure-integration-lab/providers/Microsoft.Storage/storageAccounts/saaiazureintegrationlab' --output none
```

The private `function-deployments` container was created in `saaiazureintegrationlab` using the Azure Storage MCP operation `storage_blob_container_create`; the returned `publicAccess` was `None`. It was required because the first retry reported `ContainerNotFound`. The account-level Storage Blob Data Contributor assignment already existed for this UAMI and supplied deployment-package write access.

### Create the Flex Consumption app

```powershell
az functionapp create `
  --resource-group rg-ai-azure-integration-lab `
  --name day2fnsprint29 `
  --storage-account saaiazureintegrationlab `
  --runtime python `
  --runtime-version 3.14 `
  --functions-version 4 `
  --flexconsumption-location centralindia `
  --instance-memory 512 `
  --maximum-instance-count 1 `
  --assign-identity '/subscriptions/e5939949-6509-48de-964b-5f1b65c34714/resourcegroups/rg-ai-azure-integration-lab/providers/Microsoft.ManagedIdentity/userAssignedIdentities/uami-agentic-ai-lab-storage' `
  --deployment-storage-name saaiazureintegrationlab `
  --deployment-storage-container-name function-deployments `
  --deployment-storage-auth-type UserAssignedIdentity `
  --deployment-storage-auth-value '/subscriptions/e5939949-6509-48de-964b-5f1b65c34714/resourcegroups/rg-ai-azure-integration-lab/providers/Microsoft.ManagedIdentity/userAssignedIdentities/uami-agentic-ai-lab-storage' `
  --disable-app-insights false `
  --subscription e5939949-6509-48de-964b-5f1b65c34714
```

The app’s deployment configuration was subsequently verified as `UserAssignedIdentity` with the `function-deployments` Blob container. The plan’s ARM SKU was verified as `FC1`.

### Configure identity-based storage and remove the legacy setting

```powershell
az functionapp config appsettings set --name day2fnsprint29 --resource-group rg-ai-azure-integration-lab --settings `
  'BLOB_STORAGE_ACCOUNT_URL=https://saaiazureintegrationlab.blob.core.windows.net/' `
  'BLOB_CONTAINER_NAME=incoming' `
  'AzureWebJobsStorage__accountName=saaiazureintegrationlab' `
  'AzureWebJobsStorage__credential=managedidentity' `
  'AzureWebJobsStorage__clientId=d45e36bc-698a-4cf2-9943-96eea26bd4d4'

az functionapp config appsettings delete --name day2fnsprint29 --resource-group rg-ai-azure-integration-lab --setting-names AzureWebJobsStorage

az functionapp config appsettings set --name day2fnsprint29 --resource-group rg-ai-azure-integration-lab --settings `
  'AZURE_CLIENT_ID=d45e36bc-698a-4cf2-9943-96eea26bd4d4'
```

Flex Consumption rejected `FUNCTIONS_WORKER_RUNTIME` as an invalid app setting because runtime is part of the Flex `functionAppConfig`; Python 3.14 was already set by `az functionapp create`. The failed setting operation was corrected without adding that setting. The local-only `local.settings.json` (including its `UseDevelopmentStorage=true`) was excluded from the deployment package.

### Package and deploy

The package contained only the project-root files `function_app.py`, `host.json`, and `requirements.txt`. It excluded `.venv`, `local.settings.json`, and editor files. The deployment used remote Linux build so Python dependencies were resolved for the Linux runtime rather than copied from Windows.

```powershell
az functionapp deployment source config-zip `
  --name day2fnsprint29 `
  --resource-group rg-ai-azure-integration-lab `
  --src '<path-to-day2-function-deploy.zip>' `
  --build-remote true `
  --subscription e5939949-6509-48de-964b-5f1b65c34714 `
  --timeout 180000
```

Azure reported `Deployment was successful.` The package deployment was accepted with HTTP 202, then trigger synchronization and app health checks completed.

### Validate the deployed Function without exposing its key

The Function retains the source decorator’s `auth_level=func.AuthLevel.FUNCTION`. A Function key was obtained in memory and sent in the `x-functions-key` header; the key was not written into the project, settings, or this document.

```powershell
$key = az functionapp function keys list --name day2fnsprint29 --resource-group rg-ai-azure-integration-lab --function-name BlobIdentityDemo --query default -o tsv
Invoke-RestMethod -Uri 'https://day2fnsprint29.azurewebsites.net/api/BlobIdentityDemo' -Headers @{ 'x-functions-key' = $key }
```

Observed evidence:

- The Function was indexed in Azure as `day2fnsprint29/BlobIdentityDemo` with `authLevel: FUNCTION`.
- The authorized HTTPS invocation returned `Container 'incoming' contains 0 blob(s):` (HTTP 200).
- Azure ARM reported runtime `python` version `3.14`, plan SKU `FC1`, 512 MB instance memory, maximum instance count `1`, and `alwaysReady: []`.
- Azure deployment configuration reported `UserAssignedIdentity` and the existing UAMI resource ID for deployment storage.
- The Function App identity listing contained the existing UAMI; no system-assigned identity or second UAMI was added.
- The settings check found `AzureWebJobsStorage__accountName`, `__credential`, and `__clientId`; a plain `AzureWebJobsStorage` setting was absent.
- The UAMI had `Storage Blob Data Contributor` and `Storage Blob Data Owner` at the existing storage-account scope.

## Current Microsoft references

- [Flex Consumption plan hosting](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan) — recommended serverless Functions plan, scale-to-zero, optional always-ready instances, and billing model.
- [Manage connections and identity-based host storage](https://learn.microsoft.com/en-us/azure/azure-functions/manage-connections) — `AzureWebJobsStorage__*` settings, UAMI selection, and host-storage permissions.
- [Create and manage Flex Consumption apps](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to) — app creation and identity-based deployment storage.
- [Python build options](https://learn.microsoft.com/en-us/azure/azure-functions/python-build-options) — remote build recommendation for Python deployment from Windows to Linux.
- [Supported Functions languages](https://learn.microsoft.com/en-us/azure/azure-functions/supported-languages) — Python 3.14 support.
- [Azure Functions pricing](https://azure.microsoft.com/en-us/pricing/details/functions/) — current Flex Consumption meters and monthly on-demand grant.
- [Azure Monitor pricing](https://azure.microsoft.com/en-us/pricing/details/monitor/) — telemetry ingestion and retention pricing.

## Review checkpoint

No commit or push was made. Review the shared-account host/business storage arrangement and the account-scope Blob Data Owner assignment as part of the resulting state. The deployed Function currently supports the single required HTTP demonstration; expanding its trigger/binding set may require additional host-storage roles.

## Infrastructure as code

The repository includes [Bicep](../../infra/day2-function.bicep), a [parameter file](../../infra/day2-function.bicepparam), and an [infrastructure README](../../infra/README.md) describing the current Flex Consumption plan, Function App, identity-based host and deployment storage, existing Application Insights component, private deployment container, and existing storage role assignments. The template references the existing storage account and UAMI rather than creating duplicates.

The Bicep template was applied as resource-group deployment day2-function-infrastructure on 2026-09-30. Azure reported provisioningState: Succeeded; outputs confirmed plan SKU FC1 and hostname day2fnsprint29.azurewebsites.net. The deployment reused the existing storage account, UAMI, Application Insights component, and role assignments. Post-deployment checks confirmed httpsOnly: true and an authorized HTTPS invocation returned HTTP 200 with Container 'incoming' contains 0 blob(s):. No commit or push has been made.