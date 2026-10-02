# Azure Integration Sprint — Day 5: Blob events through Event Grid to Service Bus

**Date:** 2 October 2026 (Asia/Kolkata)
**Status:** Implemented and runtime-validated on 2 October 2026.

## Objective and architecture

Extend the Day 4 queue path so a Blob creation in the existing incoming container starts asynchronous processing:

    Existing Storage account / incoming container
      → BlobCreated event
      → Event Grid Storage system topic
      → system-assigned managed identity
      → existing Service Bus queue integration-events
      → existing Function App day2fnsprint29 / ServiceBusQueueConsumer

Day 5 creates no Service Bus namespace, queue, Function App, Storage account, or user-assigned identity. It adds an Event Grid system topic, one subscription, and one queue-scoped role assignment. The Function consumer remains the Day 4 consumer and logs only message metadata, never the event payload.

## Readiness and design checkpoints

The work started from docs/azure-sprint-day-04 at 76ddd9d; the only pre-existing working-tree change was day2-function/function_app.py. It is the Day 2 auth-level edit and was left unstaged and untouched. Day 5 work is isolated on docs/azure-sprint-day-05.

Read-only Azure checks confirmed the enabled subscription, existing Central India resource group, Storage account saaiazureintegrationlab, Service Bus namespace sb-ai-int-likwmn7js4ffw, queue integration-events, Function App day2fnsprint29, and indexed trigger ServiceBusQueueConsumer. The queue started with zero active and zero dead-letter messages. The Storage account already had incoming and public network access enabled. No Event Grid system topic or Storage event subscription existed. Microsoft.EventGrid was NotRegistered; it was registered for this lab.

The checkpoint compared direct Blob-to-Function delivery, Blob-to-Event-Grid-to-Service-Bus delivery, and a separate custom topic. Reuse of the Day 4 queue and consumer made the Storage system-topic path the smallest useful extension. Event Grid detects, filters and routes the state change; Service Bus remains the durable work buffer and the Function remains the consumer.

## Reasoning, prompts, and decisions

- Reuse check: the user confirmed the Day 4 namespace and asked to continue against existing Azure resources. Live inventory verified the exact queue and Function trigger before the build.
- Provider checkpoint: Event Grid was not registered. Registration was completed before resource deployment.
- Identity checkpoint: a system-assigned identity on the Storage system topic avoids a new identity resource. Its Service Bus Data Sender grant is scoped to integration-events.
- Filter checkpoint: subscribe only to Microsoft.Storage.BlobCreated events whose subject begins with /blobServices/default/containers/incoming/blobs/. This excludes other containers, including Function host and deployment containers.
- Error-handling checkpoint: the first template draft included an Event Grid Blob dead-letter destination. The subscription failed with a managed-identity authorization error for the dead-letter endpoint. Current Microsoft guidance calls for Storage Blob Data Contributor on the Storage account for this dead-letter path. Since this is a shared account, that grants broader data access than the lab warrants. The dead-letter destination, its role, and its dedicated container were removed; the partial container and assignment were cleaned up. Event Grid retry remains configured. No delivery failure was deliberately induced.
- Consumer checkpoint: the existing Function handler decodes UTF-8 and returns successfully, allowing the Service Bus extension to complete the message. Its log contains message ID, content type, and byte count only.

See ADR 0005 for the durable choice.

## Concepts

- Event Grid provides event notification, event-type and subject filtering, and push routing. It does not replace a durable work queue.
- Service Bus provides durable asynchronous buffering between event routing and processing. Its existing lock, retry, and Service Bus dead-letter behavior continue to apply.
- Treat Event Grid delivery and Service Bus processing as at-least-once. Consumers should be idempotent before doing non-repeatable business work.
- The subscription is configured for at most 10 delivery attempts and a 1,440-minute event TTL; the first limit reached ends delivery. This is configuration evidence, not a forced-failure test.
- No Event Grid Blob dead-letter destination is configured. Non-retryable delivery errors can be dropped without one. Service Bus still has its independent dead-letter subqueue.
- The system topic authenticates as its own managed identity. Azure RBAC grants that identity Service Bus Data Sender on only the target queue.
- Do not assume event ordering. Consumers should use event IDs and Blob metadata to make work safe to repeat.

## Infrastructure and reproduction

From the repository root, set the intended subscription, verify the target, compile and validate the incremental template, inspect the what-if result, then deploy:

    az account set --subscription e5939949-6509-48de-964b-5f1b65c34714
    az account show --query "{id:id,state:state}" -o json
    az provider show --namespace Microsoft.EventGrid --query registrationState -o tsv
    az provider register --namespace Microsoft.EventGrid --wait
    az provider show --namespace Microsoft.EventGrid --query registrationState -o tsv
    az bicep build --file infra/day5-eventgrid.bicep
    az deployment group validate --name day5-eventgrid-validation --resource-group rg-ai-azure-integration-lab --template-file infra/day5-eventgrid.bicep
    az deployment group what-if --name day5-eventgrid --resource-group rg-ai-azure-integration-lab --template-file infra/day5-eventgrid.bicep
    az deployment group create --name day5-eventgrid --resource-group rg-ai-azure-integration-lab --template-file infra/day5-eventgrid.bicep --query properties.outputs -o json

Review that only the Storage system topic, system-topic event subscription, and queue-scoped Event Grid sender assignment are created. The template references the Storage account, Service Bus namespace, and queue as existing resources. It filters to BlobCreated events in incoming, uses the system-topic identity for delivery, and sets retry to 10 attempts / 1,440 minutes. The ARM what-if command returned no rendered output in this environment; ARM validation did return the resource/dependency list, and the deployment was incremental. Do not treat a blank what-if response as a successful preview.

### Smoke test and verification

A small non-sensitive test marker was uploaded to incoming, observed through Azure Monitor, and deleted after verification. The executed marker name was day5-eg-20261002-a7c3f11e.txt:

    az storage blob upload --account-name saaiazureintegrationlab --container-name incoming --name day5-eg-20261002-a7c3f11e.txt --file work/day5-eventgrid-validation.txt --auth-mode login --overwrite false
    az eventgrid system-topic event-subscription list --system-topic-name eg-saaiazureintegrationlab --resource-group rg-ai-azure-integration-lab
    az servicebus queue show --resource-group rg-ai-azure-integration-lab --namespace-name sb-ai-int-likwmn7js4ffw --name integration-events --query "{active:countDetails.activeMessageCount,deadLetter:countDetails.deadLetterMessageCount}" -o json
    az monitor metrics list --resource /subscriptions/e5939949-6509-48de-964b-5f1b65c34714/resourceGroups/rg-ai-azure-integration-lab/providers/Microsoft.EventGrid/systemTopics/eg-saaiazureintegrationlab --metric MatchedEventCount,DeliverySuccessCount,DeliveryAttemptFailCount,DeadLetteredCount --start-time 2026-10-02T01:45:00Z --end-time 2026-10-02T02:15:00Z --interval PT1M --aggregation Total
    az storage blob delete --account-name saaiazureintegrationlab --container-name incoming --name day5-eg-20261002-a7c3f11e.txt --auth-mode login --delete-snapshots include

Never place keys, tokens, Function keys, callback URLs, or event payloads in command output or documentation.

## Validation evidence

| Check | Evidence | Meaning |
|---|---|---|
| Subscription and existing resources | Enabled subscription; Central India group; expected Storage, namespace, queue and Function present | Correct target and reuse |
| Event Grid readiness | Provider changed from NotRegistered to Registered | Provider ready |
| Existing queue/consumer | Queue integration-events; Function index lists ServiceBusQueueConsumer bound to that queue | Consumer identified before build |
| Template | Bicep build passed; final ARM group validation succeeded; deployment day5-eventgrid succeeded | Corrected template accepted |
| Managed identity and RBAC | System topic identity enabled; Azure Service Bus Data Sender assignment exists at exact queue scope | Identity delivery without SAS; least-privilege queue grant |
| Subscription configuration | Provisioning Succeeded; ServiceBusQueue endpoint is the existing queue; system-assigned delivery identity; BlobCreated + incoming filter; retry policy 10 attempts / 1,440 minutes | Intended route active |
| Actual Blob event | Uploaded marker to incoming; Event Grid metrics for 2026-10-02 02:06Z showed MatchedEventCount 1 and DeliverySuccessCount 1 | Event matched and Event Grid delivered it |
| Delivery errors | DeliveryAttemptFailCount and DeadLetteredCount had no data series for the test interval | No failed delivery or Event Grid dead-letter observed during the happy-path test |
| Consumer outcome | Queue showed 0 active and 0 dead-letter messages shortly after successful delivery; the only queue trigger is the existing Function | Consistent with Function consumption/completion; direct Application Insights trace was not verified |
| Cleanup | Smoke-test blob deleted; queue remained 0 active / 0 dead-letter; temporary dead-letter container and role assignment removed | No test message or unused dead-letter resource left behind |
| Local quality gates | Ruff passed; pytest passed all 6 tests at 100% coverage | Existing Python checks pass; source remained unchanged |
| PR / CI / review | PR #6 is open; required Python quality check passed. No formal review is recorded. GitHub reports main is not protected. | Do not merge until the review and main-branch protection mismatch are resolved |

The Application Insights CLI query was not run because this Azure CLI installation did not have the optional application-insights extension and prompted for an interactive install. The extension was not installed. Runtime evidence uses built-in Azure Monitor Event Grid metrics and Service Bus queue counts.

## Security and cost

- Event Grid uses a system-assigned managed identity; no SAS key or connection string was added.
- The Event Grid identity has only Azure Service Bus Data Sender on the one queue. Existing Function Data Receiver access is unchanged.
- Source filtering confines the subscription to the existing incoming business container. No Storage data role was granted to Event Grid.
- The Service Bus namespace remains local-auth disabled and TLS 1.2 minimum. Event Grid managed-identity delivery does not support private endpoints for this delivery leg; current shared services use public endpoints.
- Event Grid Basic is pay-per-operation. Pricing counts published events and delivery attempts; check live Event Grid India pricing and subscription offer before scaling. One smoke event produced one match and one successful delivery. No exact currency cost is claimed.
- No new Service Bus namespace/base charge, compute, identity, storage account, or monitoring resource was added. The existing Standard Service Bus charge continues unchanged. Storage write/delete transactions and Function execution/telemetry are usage-based.
- Event Grid has retry configured but no Blob dead-letter storage. Monitor DeliveryAttemptFailCount and DroppedEventCount. For production dead-lettering, use a dedicated Storage account or approve the broader Storage account role after a security review.

## Cleanup and rollback

These commands remove only Day 5 resources and the Event Grid queue grant. They do not delete the shared group or Day 4 queue/namespace/Function:

    $principal = az eventgrid system-topic show --resource-group rg-ai-azure-integration-lab --name eg-saaiazureintegrationlab --query identity.principalId -o tsv
    $queue = az servicebus queue show --resource-group rg-ai-azure-integration-lab --namespace-name sb-ai-int-likwmn7js4ffw --name integration-events --query id -o tsv
    az role assignment delete --assignee $principal --role "Azure Service Bus Data Sender" --scope $queue
    az eventgrid system-topic delete --resource-group rg-ai-azure-integration-lab --name eg-saaiazureintegrationlab

Verify the Event Grid system topic, subscription, and queue-scoped assignment are gone. Keep Microsoft.EventGrid registered; provider registration itself has no running resource charge. The Day 4 namespace and queue are shared sprint dependencies and must be retained unless separately approved for cleanup.

## Troubleshooting checkpoints

- Provider or topic errors: confirm Microsoft.EventGrid is Registered and the Storage System Topic is provisioned.
- 401/403 destination authorization: verify the topic identity, queue resource ID, Azure Service Bus Data Sender role, exact queue scope, and RBAC propagation. Do not switch to SAS.
- Blob does not match: check Microsoft.Storage.BlobCreated and the exact incoming subject prefix. Use a new blob create for this test.
- No delivery: inspect Event Grid DeliveryAttemptFailCount, DroppedEventCount, and subscription provisioning state; then inspect queue and Function host health.
- Function does not consume: check Function indexing, identity-based Service Bus settings, queue name, receiver scope, extension bundle, and trigger logs.
- Dead-letter requirement: Event Grid Blob dead-letter delivery requires Storage Blob Data Contributor on the Storage account in the currently documented system-topic pattern. Do not grant it on a shared account without security review. The Service Bus entity has its own independent DLQ.

## Interview takeaways

- “I used Event Grid to detect and filter BlobCreated events, then routed them into an existing Service Bus queue so the consumer could process work asynchronously.”
- “I reused the Day 4 namespace, queue and Function rather than duplicating compute or messaging infrastructure.”
- “I used a system-assigned identity and granted Service Bus Data Sender only at queue scope; the Function's receiver permission stayed separate.”
- “I validated a real event with Event Grid matched/delivered metrics and the queue returning to zero.”
- “I rejected a dead-letter design that required broad Storage data permissions on a shared account. Retry is configured, but production would need an isolated dead-letter store and alerts.”
- “Event Grid and Service Bus have separate retry/dead-letter semantics. I would design the consumer to be idempotent because delivery can repeat.”

## Tools and technology

- Azure CLI 2.88.0: provider/resource inspection, Bicep build, ARM validation/deployment, Event Grid subscription inspection, queue counts, Blob smoke test, and Azure Monitor metrics.
- Bicep / ARM: infra/day5-eventgrid.bicep references existing Storage and Service Bus resources; declares the system topic, subscription, and deterministic queue-scoped role assignment.
- Azure Event Grid Basic / Storage system topic: event filtering, managed-identity delivery, retry policy, and delivery metrics.
- Azure Service Bus Standard: reused Day 4 queue; no namespace or queue redeployment.
- Azure Functions Python v2: existing Service Bus trigger consumer; no Function code or settings changed.
- Entra managed identity / Azure RBAC: system-topic identity with queue-scoped Data Sender; no new user-assigned identity or secret.
- Git / GitHub: isolated Day 5 branch created. GitHub CLI authentication failed during this run; PR, required CI, review, merge, and final commit remain pending until authentication is restored.

## Sources

- [Event Grid managed-identity delivery](https://learn.microsoft.com/en-us/azure/event-grid/managed-service-identity)
- [Event Grid system topics](https://learn.microsoft.com/en-us/azure/event-grid/system-topics)
- [Event Grid delivery and retry](https://learn.microsoft.com/en-us/azure/event-grid/delivery-and-retry)
- [Monitor Event Grid delivery](https://learn.microsoft.com/en-us/azure/event-grid/monitor-event-delivery)
- [Event Grid Service Bus handler](https://learn.microsoft.com/en-us/azure/event-grid/handler-service-bus)
- [Service Bus managed identities and RBAC scope](https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-managed-service-identity)
- [Event Grid India pricing](https://azure.microsoft.com/en-in/pricing/details/event-grid/)

## Next-lab dependency

Day 6 can build on this path to study consumer idempotency, controlled poison-message delivery, the Service Bus dead-letter subqueue, and replay. Retain the Day 4 namespace and Day 5 subscription while using that dependency, or remove the Day 5 system topic/subscription when minimizing event operation charges.
