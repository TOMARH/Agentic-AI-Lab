# Azure sprint: Day 1 — Cost guardrails and subscription readiness

## Goal

Establish a low-risk Azure learning boundary before provisioning anything. Day 1 is complete when the subscription and spending model are understood, an appropriate budget and alerts are configured (if the account supports them), and the first lab has a written cleanup plan.

## Guardrails

1. **Identify the subscription and offer first.** Record the offer type, billing currency, whether credits or a spending limit apply, and who receives billing alerts. Do not remove or upgrade a spending limit as part of this lab.
2. **Use a monthly budget before deployment.** Review the existing subscription budget and decide whether it is sufficient for the lab; create a separate learning budget only if needed. Record its currency, scope, owner, and reset date. Do not treat an Azure budget as a spending cap: budget alerts inform you but do not stop consumption by themselves.
3. **Review actual and forecast alerts.** The verified monthly subscription budget has actual-cost alerts at 25%, 50%, 75%, and 90%. Confirm the recipients in the Portal. Forecast alert thresholds remain unverified; configure them if needed before provisioning. Azure cost evaluation and alert delivery can be delayed, so retain a manual check before and after labs.
4. **Keep the first lab small and short-lived.** Use a dedicated resource group, consistent tags (`Project=Agentic-AI-Lab`, `Environment=Learning`, `Owner`, `ExpiresOn`), and only the resources required by the lab. Prefer free/low-cost options only after confirming their limits and region availability.
5. **Clean up and verify.** Delete lab resources after validation unless the next exercise needs them. Recheck Cost Analysis and free-tier usage after cleanup; residual charges can persist for storage, logs, public IPs, or other retained resources.
6. **No secrets in Git.** Azure credentials, subscription IDs if treated as sensitive in the environment, API keys, and exported access tokens do not belong in committed files. Use identity-based authentication in later labs where suitable.

## Day 1 checklist

- [ ] Sign in to Azure Portal and identify the correct directory and subscription; record only a safe display name and offer type in lab notes.
- [ ] Confirm billing currency, remaining credits, spending-limit status, and notification contacts.
- [ ] Open Cost Management + Billing → Cost Management → Budgets and inspect current month-to-date cost and forecast.
- [ ] Review the existing subscription budget before creating any additional budget; document a separate learning-only budget only if one is needed.
- [ ] Verify recipients for the configured actual-cost alerts at 25%, 50%, 75%, and 90%; review or configure forecast alerts before provisioning.
- [ ] Confirm whether an existing subscription spending limit applies. Leave it unchanged.
- [ ] Create no paid resources until the budget and alerts are confirmed. If the offer does not support the desired budget/alerts, pause provisioning and use manual cost checks plus the offer's native controls.
- [ ] Record the baseline and guardrail decisions in the sprint notes.

## Day 1 design exercise

Draw the boundary for the first Azure lab without deploying it:

```text
Azure subscription
├── configured monthly budget (subscription scope)
└── existing resource group: `rg-ai-azure-integration-lab`
    ├── tags: unverified
    └── existing storage account: `saaiazureintegrationlab`
        └── proposed Azure Queue Storage queue (not created)
```

**Design-only proposal: Azure Queue Storage.** Add a queue to the existing storage account to let a later lab decouple a producer from a background worker. Confirm that the account supports the selected queue service and review its configuration and pricing before use. Keep messages non-sensitive and short-lived; set a retention/cleanup plan, identify producer and worker dependencies, and delete the proposed queue after the exercise if no longer needed. Check for residual costs from retained data, transactions, redundancy, and any dependent compute. The resource group and storage account already exist; the queue is only a proposal and has not been created.

For any proposed resource, record its purpose, region, pricing meter, expected hours/days active, data retention, dependencies, deletion procedure, and likely residual-cost sources. Estimate cost with the Azure Pricing Calculator immediately before provisioning; prices and free offers vary by region, offer, and date.

## Decision record to fill in

- Subscription offer/type:
- Billing currency:
- Existing spending limit / credit (do not include account secrets):
- Separate learning-only budget (if any):
- Alert recipients confirmed:
- Existing subscription budget and scope:
- Actual-cost alert thresholds / forecast thresholds:
- First lab resource and region (not deployed on Day 1):
- Cleanup owner and date:

## Day 1 verified status

This record reflects project evidence and Azure Portal details shared in the conversation as of 2026-09-28. Values that could not be verified are called out explicitly; only the listed actual-cost thresholds are confirmed as configured.

| Item | Verified status |
|---|---|
| Current monthly subscription budget | `budget-agentic-ai-lab-sub-monthly`; ₹19,109.25; monthly reset; expires October 19, 2026 (confirmed by Azure Portal evidence shared in the conversation). |
| Previous budget cleanup | `AzureIntegrationServices-HandOn` was deleted (confirmed by Azure Portal evidence shared in the conversation). |
| Separate learning-only budget | No separate project-only budget was identified in the evidence; the verified subscription budget is listed above. |
| Actual-cost alert thresholds | 25%, 50%, 75%, and 90% are configured (confirmed by Azure Portal evidence shared in the conversation). Forecast alert thresholds remain unverified. |
| Azure subscription details | Not verified. The budget evidence confirms a subscription-scoped budget and its amount in rupees, but does not establish the subscription display name, offer, credits, or spending-limit status. The Azure CLI account query could not run because its profile was denied access. |
| Azure resources | Portal evidence confirms resource group `rg-ai-azure-integration-lab` and storage account `saaiazureintegrationlab` exist. Their tags are unverified; the Queue Storage queue remains a proposal. A complete resource inventory is unavailable because CLI listing could not run with the inaccessible profile. |
| Day 1 provisioning and cleanup | No new lab resources were created as part of this documentation update. The previous budget deletion is recorded above; this does not verify whether other resources already exist in the subscription. |

Before treating Day 1 guardrails as complete, confirm the subscription, budget, thresholds, alert recipients, and resource inventory in an authorized Azure Portal or CLI session. Record only non-secret details here.

## Tools & Technology notes

See the shared [Tools & Technology inventory](../tools/README.md) for the project tool list and session notes. For this Day 1 check, Azure CLI (`az`) was present on PATH, but commands could not access its profile due to a permission error. Azure Portal evidence shared in the conversation confirms the subscription-scoped monthly budget, deletion of the previous budget, resource group `rg-ai-azure-integration-lab`, and storage account `saaiazureintegrationlab`. Resource tags and the complete resource inventory remain unverified. Do not copy profile contents, credentials, tokens, or other secrets into this document.

## Evidence and limitations

Azure budgets are alerting and accountability tools; budget alerts do not automatically stop resource usage. A subscription spending limit, when available for the offer, is a distinct mechanism with different service-impact behavior. Cost reporting and free-service usage can be delayed. Confirm current offer-specific behavior in the Azure portal before relying on it.
