# Azure sprint: Day 1 — Cost guardrails and subscription readiness

## Goal

Establish a low-risk Azure learning boundary before provisioning anything. Day 1 is complete when the subscription and spending model are understood, an appropriate budget and alerts are configured (if the account supports them), and the first lab has a written cleanup plan.

## Guardrails

1. **Identify the subscription and offer first.** Record the offer type, billing currency, whether credits or a spending limit apply, and who receives billing alerts. Do not remove or upgrade a spending limit as part of this lab.
2. **Set a monthly learning budget before deployment.** Choose an amount affordable to lose for the month. Record currency, scope, owner, and reset date. Do not treat an Azure budget as a spending cap: budget alerts inform you but do not stop consumption by themselves.
3. **Configure actual and forecast alerts.** Suggested checkpoints are 50%, 75%, 90%, and 100% of the chosen budget, routed to an actively monitored email. Verify the budget appears at the intended subscription or resource-group scope. Azure cost evaluation and alert delivery can be delayed, so retain a manual check before and after labs.
4. **Keep the first lab small and short-lived.** Use a dedicated resource group, consistent tags (`Project=Agentic-AI-Lab`, `Environment=Learning`, `Owner`, `ExpiresOn`), and only the resources required by the lab. Prefer free/low-cost options only after confirming their limits and region availability.
5. **Clean up and verify.** Delete lab resources after validation unless the next exercise needs them. Recheck Cost Analysis and free-tier usage after cleanup; residual charges can persist for storage, logs, public IPs, or other retained resources.
6. **No secrets in Git.** Azure credentials, subscription IDs if treated as sensitive in the environment, API keys, and exported access tokens do not belong in committed files. Use identity-based authentication in later labs where suitable.

## Day 1 checklist

- [ ] Sign in to Azure Portal and identify the correct directory and subscription; record only a safe display name and offer type in lab notes.
- [ ] Confirm billing currency, remaining credits, spending-limit status, and notification contacts.
- [ ] Open Cost Management + Billing → Cost Management → Budgets and inspect current month-to-date cost and forecast.
- [ ] Choose and document a monthly lab budget before creating resources.
- [ ] Create a subscription-level budget if supported; add actual and forecast notifications at the selected thresholds and verify recipients.
- [ ] Confirm whether an existing subscription spending limit applies. Leave it unchanged.
- [ ] Create no paid resources until the budget and alerts are confirmed. If the offer does not support the desired budget/alerts, pause provisioning and use manual cost checks plus the offer's native controls.
- [ ] Record the baseline and guardrail decisions in the sprint notes.

## Day 1 design exercise

Draw the boundary for the first Azure lab without deploying it:

```text
Azure subscription
└── dedicated learning resource group
    ├── budget scope and cost tags
    └── proposed Azure Queue Storage account/queue (design only; not deployed)
```

**Design-only proposal: Azure Queue Storage.** Use one queue to let a later lab decouple a producer from a background worker. Choose the storage account type, redundancy, and region only after confirming the lab's requirements and current pricing. Keep messages non-sensitive and short-lived; set a retention/cleanup plan, identify the producer and worker dependencies, and delete the queue and account after the exercise. Check for residual costs from retained data, transactions, redundancy, and any dependent compute. This is a proposal only: no storage account or queue has been created.

For any proposed resource, record its purpose, region, pricing meter, expected hours/days active, data retention, dependencies, deletion procedure, and likely residual-cost sources. Estimate cost with the Azure Pricing Calculator immediately before provisioning; prices and free offers vary by region, offer, and date.

## Decision record to fill in

- Subscription offer/type:
- Billing currency:
- Existing spending limit / credit (do not include account secrets):
- Monthly learning budget:
- Alert recipients confirmed:
- Budget scope and thresholds:
- First lab resource and region (not deployed on Day 1):
- Cleanup owner and date:

## Day 1 verified status

This record reflects evidence available in the project workspace on 2026-09-28. No authenticated Azure Portal session or verified Portal values were available during this update. Values that could not be verified are called out explicitly; do not treat the suggested thresholds above as configured alerts.

| Item | Verified status |
|---|---|
| Monthly learning budget | Not recorded or verified. No amount, currency, scope, owner, or reset date is present in the project notes. |
| Alert thresholds | 50%, 75%, 90%, and 100% are planning suggestions only. No configured budget or actual/forecast alert was verifiable. |
| Azure subscription | Not verified. No authenticated Portal session was available, and the Azure CLI read-only account query could not run because the CLI profile was denied access. No subscription identifier or account details were read or copied. |
| Azure resource inventory | Not verified. The Portal was unavailable and CLI resource listing could not run because the profile was inaccessible; this record does not assert that the subscription has no resources. |
| Day 1 provisioning | No Azure resources were provisioned as part of this workspace documentation update. |

Before treating Day 1 guardrails as complete, confirm the subscription, budget, thresholds, alert recipients, and resource inventory in an authorized Azure Portal or CLI session. Record only non-secret details here.

## Tools & Technology notes

See the shared [Tools & Technology inventory](../tools/README.md) for the project tool list and session notes. For this Day 1 check, Azure CLI (`az`) was present on PATH, but commands could not access its profile due to a permission error. No authenticated Azure Portal session was available. Therefore the active account, subscription, budgets, alerts, and resource list remain unverified. Do not copy profile contents, credentials, tokens, or other secrets into this document.

## Evidence and limitations

Azure budgets are alerting and accountability tools; budget alerts do not automatically stop resource usage. A subscription spending limit, when available for the offer, is a distinct mechanism with different service-impact behavior. Cost reporting and free-service usage can be delayed. Confirm current offer-specific behavior in the Azure portal before relying on it.
