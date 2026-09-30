# Azure sprint: Day 1 — Subscription readiness, Storage, and Managed Identity

## 1. Day 1 objective

Establish the cost guardrails for the Azure learning work, inspect the existing storage baseline, create a UAMI, and configure account-scoped Blob data authorization for it. The identity and role assignment were verified. Day 1 did **not** demonstrate UAMI-based Blob access from an Azure-hosted workload.

## 2. Subscription and cost guardrails

The lab began with a cost-readiness checkpoint: review the existing subscription budget and its notifications before provisioning, and treat budget alerts as information rather than a hard spending cap. The existing subscription budget was sufficient as the documented guardrail; no separate learning-only budget is recorded.

| Item | Verified status |
|---|---|
| Subscription budget | `budget-agentic-ai-lab-sub-monthly` |
| Budget amount and currency | ₹19,109.25 per month |
| Reset / expiry | Monthly reset; expires October 19, 2026 |
| Actual-cost alert thresholds | 25%, 50%, 75%, and 90% configured |
| Forecast alert thresholds | Not verified in the evidence available for this lab |
| Previous budget cleanup | `AzureIntegrationServices-HandOn` had been deleted |
| Offer, credits, spending-limit status | Not verified; no such claims are made here |

The actual alert thresholds and budget details were confirmed from Azure Portal evidence shared during the lab. Alert recipients and forecast thresholds were not established in the verified record. Budgets notify; they do not themselves stop resource use. Azure cost data and alert delivery can lag, so manual review remains useful before and after lab work.

The engineering checkpoint was to keep the first exercise on already-existing resources where possible, check cost implications, and avoid treating an alert as a spending limit. No budget change is recorded as part of the storage identity work below.

## 3. Storage baseline

The existing storage account was `saaiazureintegrationlab` in Central India. Its baseline was `StorageV2` / `Standard_LRS`, HTTPS-only enabled, minimum TLS 1.2, and public Blob access disabled. The existing containers were `incoming` and `processed`.

This baseline shaped the access decision: retain private access and use an identity plus RBAC for authenticated data access. A proposed Queue Storage exercise from earlier planning was not part of the completed lab and is omitted from the final resource state.

## 4. Managed Identity

A user-assigned managed identity named `uami-agentic-ai-lab-storage` was created. Azure automatically registered the `Microsoft.ManagedIdentity` resource provider as part of this work. The identity was opened and verified in Azure Portal.

A UAMI has a lifecycle independent of a particular compute resource and can be attached to an Azure-hosted workload later. Its creation and portal verification establish the identity resource; they do not prove that a workload can obtain its token or use it against Blob Storage.

## 5. Authentication vs authorization

Authentication establishes **who** is making a request. Authorization determines **what** that identity can do and **where** it can do it. The UAMI is the security principal. The Blob data role assignment is the authorization rule. Creating the identity alone does not grant storage access, and assigning a role alone does not prove token acquisition or successful data operations from a workload.

## 6. RBAC and least privilege

`Storage Blob Data Contributor` was assigned to the UAMI. This is a Blob data-plane role, separate from management-plane roles used to manage the storage account resource. The assignment scope is the storage account only.

The scope decision was to grant the needed Blob role on `saaiazureintegrationlab`, rather than at resource-group or subscription scope, to constrain the identity's access to the intended account. A narrower container scope could be evaluated later if the workload's needs and setup support it. The account's public Blob access remains disabled.

### Commands: executed/verified, reproduction-only, and rollback-only

#### Actually executed/verified during the lab

The lab record confirms these operations were executed and verified during the lab:

- Inspected storage account `saaiazureintegrationlab` and its configuration.
- Listed the storage account's containers; `incoming` and `processed` were present.
- Listed and verified the user-assigned identity `uami-agentic-ai-lab-storage` in Azure CLI; the identity was also verified in Azure Portal.
- Created `uami-agentic-ai-lab-storage`. Azure automatically registered `Microsoft.ManagedIdentity` during identity creation.
- Created a `Storage Blob Data Contributor` role assignment for the UAMI at the storage-account scope.
- Verified the role assignment through Azure CLI.
- Listed the final resource inventory; it contained only the storage account and UAMI.

Only the verified operations and outcomes are stated here. The separately labeled reproduction section provides command examples and is not presented as the literal transcript of these executed commands.

#### Reproduction-only commands

These commands are provided only to reproduce the setup. They are distinct from the operations executed and verified above. Set `$resourceGroup` to the resource group's actual name and sign in to the intended subscription first.

```powershell
$resourceGroup = "<existing-resource-group>"
$accountName = "saaiazureintegrationlab"
$identityName = "uami-agentic-ai-lab-storage"
$subscriptionId = (az account show --query id --output tsv)
$accountId = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.Storage/storageAccounts/$accountName"

# Inspect the account baseline
az storage account show --resource-group $resourceGroup --name $accountName --output json

# Create the UAMI; Azure registers Microsoft.ManagedIdentity if needed
az identity create --resource-group $resourceGroup --name $identityName --location centralindia --output json

# Assign the Blob data role at account scope
$principalId = (az identity show --resource-group $resourceGroup --name $identityName --query principalId --output tsv)
az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal --role "Storage Blob Data Contributor" --scope $accountId --output json
```

### Working prompts and architectural checkpoints

- Establish cost guardrails before provisioning; review the existing budget and alerts without treating alerts as a spending cap.
- Keep the repository and Azure resource footprint clean; avoid unrelated files and unnecessary resources.
- Use a UAMI instead of embedding credentials in workload configuration.
- Verify identity existence and RBAC authorization independently; neither check substitutes for the other.
- Do not create extra Azure infrastructure merely to manufacture proof of workload Blob access; defer that demonstration to a lab with a real workload need.
- Record meaningful setup decisions, commands, and verification checkpoints so the work can be reproduced later.

## 7. Validation evidence

- **Cost readiness:** Azure Portal evidence shared during the lab showed the monthly subscription budget, ₹19,109.25 amount, monthly reset, October 19, 2026 expiry, and configured 25%, 50%, 75%, and 90% actual-cost alerts. Forecast alert thresholds and recipients were not verified in the documented evidence.
- **Storage baseline:** the existing account properties and its `incoming` and `processed` containers are the recorded baseline.
- **Identity:** `uami-agentic-ai-lab-storage` was verified in Azure Portal.
- **Provider:** `Microsoft.ManagedIdentity` was automatically registered during identity creation.
- **RBAC:** Azure CLI verification confirmed `Storage Blob Data Contributor` for the UAMI at the storage-account scope.
- **Inventory:** final Azure CLI inventory contained only the storage account and the UAMI.
- **Workload access:** Actual UAMI-based Blob access from an Azure-hosted workload has NOT been demonstrated.

## 8. Architecture decisions / ADRs

### ADR 1 — Cost guardrail

**Decision:** Use the existing monthly subscription budget and its configured actual-cost alerts as the cost-monitoring baseline; do not represent a budget as a spending cap.

**Reasoning:** The budget and alert thresholds were already in place and verified. A separate lab budget was not needed for the documented work. Unknown forecast thresholds and recipients remain unclaimed.

### ADR 2 — Identity and storage authorization

**Decision:** Create a UAMI and grant it `Storage Blob Data Contributor` at the storage-account scope.

**Reasoning:** A separately managed identity can later be attached to the workload. Account scope limits the permission boundary to the target storage account, while public Blob access remains disabled.

**Status:** Identity creation, portal verification, role assignment, and CLI verification are complete. Workload attachment, token acquisition, and Blob access are deferred to the next lab.

## 9. Cost considerations

The monthly budget is ₹19,109.25 with a monthly reset and the actual-cost thresholds listed above; these alerts inform monitoring but do not stop consumption. Storage costs can vary with stored data, transactions, redundancy, region, and enabled features. `Standard_LRS` is the configured redundancy SKU. The existing storage account and retained data may continue to incur charges; review current Azure cost data when planning further exercises. No specific spend or savings outcome is asserted.

## 10. Cleanup / rollback

No cleanup of the storage account or containers is part of this lab; both pre-existed and are needed by the next exercise. If the identity grant is to be rolled back, remove the role assignment at the same account scope, verify it is absent, and then delete the UAMI if it is no longer needed. These are rollback-only commands; they are not reproduction setup steps and were not executed during this lab:

```powershell
az role assignment delete --assignee $principalId --role "Storage Blob Data Contributor" --scope $accountId
az role assignment list --assignee $principalId --scope $accountId --include-inherited --query "[?roleDefinitionName=='Storage Blob Data Contributor']" --output table
az identity delete --resource-group $resourceGroup --name $identityName
```

Do not delete the storage account or its existing containers as part of identity rollback. The deleted budget `AzureIntegrationServices-HandOn` is recorded as prior cleanup, not as a cleanup action performed in this identity exercise.

## 11. Final resource state

The final inventory contains only:

- Storage account `saaiazureintegrationlab` (Central India, `StorageV2` / `Standard_LRS`, HTTPS-only, minimum TLS 1.2, public Blob access disabled), with existing containers `incoming` and `processed`.
- User-assigned managed identity `uami-agentic-ai-lab-storage`, with `Storage Blob Data Contributor` assigned at the storage-account scope.

No workload resource was part of the final inventory. Actual UAMI-based Blob access from an Azure-hosted workload has **NOT** been demonstrated.

## 12. Reproduction checklist

1. Sign in to the intended Azure tenant and subscription; inspect the existing budget and confirm amount, reset, expiry, alert thresholds, and recipients where available. Treat budget alerts as notifications, not a cap.
2. Locate the existing resource group and inspect `saaiazureintegrationlab` in Central India.
3. Confirm `StorageV2`, `Standard_LRS`, HTTPS-only, minimum TLS 1.2, public Blob access disabled, and containers `incoming` and `processed`.
4. Create `uami-agentic-ai-lab-storage` in Central India. Allow Azure to register `Microsoft.ManagedIdentity` if required.
5. Verify the UAMI in Azure Portal.
6. Assign `Storage Blob Data Contributor` to the UAMI at the storage account resource ID only.
7. Verify the role assignment and its scope through Azure CLI.
8. Verify the final resource inventory contains only the storage account and UAMI.
9. Keep workload access marked incomplete until an Azure-hosted workload obtains a token for the UAMI and successfully performs the intended Blob operation.
10. Review current costs and retain a rollback plan before extending the lab.

Section 6 separates commands actually executed and verified from reproduction-only setup commands. Section 10 contains rollback-only commands.

## 13. Tools & technology documentation

Azure Portal was used for cost-budget evidence and UAMI verification. Azure CLI was used to verify the RBAC assignment and resource inventory; the corresponding executed verification commands are listed in section 6. Services and concepts used include Azure Storage, Microsoft Entra managed identities, and Azure RBAC. See the shared [Tools & Technology inventory](../tools/README.md) for project-wide tool documentation.

## 14. Interview takeaways

- Authentication answers who the caller is; authorization defines permitted operations and scope.
- Managed identities let supported Azure workloads use an Azure-managed identity without storing an application secret.
- A UAMI is independently managed and can be attached to workloads, but creation does not prove workload access.
- Azure RBAC combines principal, role, and scope; Blob data-plane permissions differ from management-plane permissions.
- Least privilege includes choosing both a suitable role and the narrowest workable scope.
- A budget alert is a monitoring signal, not an automatic spending stop.
- Validate the complete path—identity availability, token acquisition, authorization, and actual data operation—before claiming access works.

## 15. Next-lab dependency

Day 2 completed this dependency: the existing UAMI was attached to an Azure-hosted Function, and the deployed Function listed the existing incoming Blob container using identity-based access. See [Azure sprint Day 2](azure-sprint-day-02.md) for the deployment record and validation evidence.
