# Azure sprint — Day 18: restore the Logic App Blob identity route

## Objective

Reconcile the portal-created Day 3 Logic App with the current Function App and make the cross-service contract durable in source control. Preserve the existing `list-blobs` HTTP function and the Day 7–8 Service Bus consumer.

## Live configuration found

The Logic App `la-day3-orchestration` calls `GET /api/blobidentitydemo` on `day2fnsprint29.azurewebsites.net` using a user-assigned managed identity with audience `https://management.azure.com`. Only after that HTTP action succeeds, it sends a `day4-integration-event` message to the existing `integration-events` Service Bus queue using managed identity. The workflow also has a failure scope for a failed or timed-out Function call.

The Function App was running but exposed only `list-blobs` and `ServiceBusQueueConsumer`. Its app settings already included `BLOB_STORAGE_ACCOUNT_URL`, `BLOB_CONTAINER_NAME`, and Service Bus managed-identity connection settings. App Service Authentication v2 is enabled, requires authentication, returns 401 to unauthenticated requests, and allows the workflow's `https://management.azure.com` audience. Therefore the Functions route can use `ANONYMOUS` auth level while the platform requires and validates the managed-identity bearer token.

The sanitized live contract is in [day18-logicapp-contract.json](../architecture/day18-logicapp-contract.json). Resource identifiers and secrets are omitted.

## Implementation

Restore `GET /api/blobidentitydemo` using the historical `BLOB_STORAGE_ACCOUNT_URL` and `BLOB_CONTAINER_NAME` settings, `DefaultAzureCredential`, and `BlobServiceClient`. Keep the JSON `list-blobs` endpoint and Service Bus consumer unchanged. The test suite verifies the compatibility handler and the route/method/order contract against the sanitized workflow record.

## Build and deploy

From the repository root, create a ZIP whose three files are at the archive root, then use Azure remote build so dependencies are resolved for the Function App's Linux runtime:

```powershell
Push-Location .\day2-function
Compress-Archive -Path function_app.py,host.json,requirements.txt -DestinationPath ..\day18-function.zip -Force
Pop-Location
az functionapp deployment source config-zip `
  --resource-group rg-ai-azure-integration-lab `
  --name day2fnsprint29 `
  --src .\day18-function.zip `
  --build-remote true
```

Do not include `.env`, `local.settings.json`, tests, or a Windows-built `.python_packages` directory. The deployed app retained its existing blob storage, App Insights, and Service Bus managed-identity app settings.

## Validation and evidence

On 16 October 2026, both repository CI test selections passed (53 repository tests; 20 Function tests), Day 2 Function coverage was 100%, and both Ruff lint commands passed. Azure accepted deployment `aadeca4f-8b82-4619-82d2-4ea6319b5316` and reported `Deployment was successful.` The deployed route catalog contained `blob_identity_demo` at `GET /api/blobidentitydemo`, `list_blobs`, and `ServiceBusQueueConsumer`. A direct unauthenticated request returned 401.

The authenticated Logic App trigger returned 202 for run `08584094467946492930675932594CU31` (started 2026-10-16 14:14:50 UTC). The run completed `Succeeded`: action `HTTP` was `Succeeded` with code `OK`; `Send_ServiceBus_Message` was `Succeeded` with code `Created`; the failure scope was skipped. App Insights recorded `blob_identity_demo` HTTP 200 and `Processing BlobIdentityDemo request.` The consumer logged `Consuming message` with ID `5735b8b0b047463abda37649bad49ace` and `DeliveryCount=1`. Queue runtime counts after processing were 0 active and 0 dead-letter messages (baseline was also 0/0).

## Limitations and operations

The Logic App's authenticated trigger URL is intentionally not exported. It must be invoked from the Azure Portal or an authorized workflow trigger client. A successful Function response confirms blob listing; a completed Service Bus send and positive consumer telemetry are separate checks. No queue cleanup or message replay is part of this lab.
