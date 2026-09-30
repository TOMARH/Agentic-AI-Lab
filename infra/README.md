# Day 2 Function infrastructure

This Bicep deployment captures the existing Azure Functions Flex Consumption setup. It manages the Flex plan, Function App, app settings, and the two storage role assignments. It references the existing Storage account, UAMI, Application Insights component, and private function-deployments container; it creates no duplicate storage account, identity, or Insights component.

`day2-function.bicepparam` contains the current lab resource names and scale settings. No keys or storage connection strings are stored in source.

## Review and deploy

From the repository root, first inspect the proposed changes:

```powershell
az deployment group what-if `
  --resource-group rg-ai-azure-integration-lab `
  --template-file infra/day2-function.bicep `
  --parameters infra/day2-function.bicepparam
```

Only after reviewing the what-if output, deploy the infrastructure:

```powershell
az deployment group create `
  --name day2-function-infrastructure `
  --resource-group rg-ai-azure-integration-lab `
  --template-file infra/day2-function.bicep `
  --parameters infra/day2-function.bicepparam
```

The day2-function-infrastructure deployment completed successfully on 2026-09-30. It reused the existing resources and role assignments; the deployment output confirmed plan SKU FC1 and hostname day2fnsprint29.azurewebsites.net. The template enforces HTTPS-only access, which was verified after deployment. Python code packaging is separate; for code updates from Windows, use the remote-build deployment command in [the Day 2 lab record](../docs/labs/azure-sprint-day-02.md).

## Existing-resource and scope notes

- The parameter file is specific to the current subscription's resource names. Review and change the parameters before using it in another environment.
- The two role-assignment resource names match the existing Azure assignment IDs so the template refers to the current grants instead of intentionally adding a second grant.
- Both roles are at the existing storage-account scope. `Storage Blob Data Contributor` predates the Function deployment; `Storage Blob Data Owner` was added for Functions host storage. Sharing the account means the host role applies across its blob data.
- The host connection uses `AzureWebJobsStorage__*`; the business SDK uses `BLOB_STORAGE_ACCOUNT_URL` and `BLOB_CONTAINER_NAME`. The two purposes are configured separately while reusing the existing account.
- The Bicep file preserves the Function key auth level through the existing application source; the app route's `FUNCTION` auth level remains defined in `day2-function/function_app.py`.
- The Function App's `APPLICATIONINSIGHTS_CONNECTION_STRING` is read from the existing Insights resource at deployment. It is not a storage credential.
