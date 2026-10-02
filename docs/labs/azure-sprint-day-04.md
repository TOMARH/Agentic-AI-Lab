# Azure Integration Sprint — Day 4: Azure Service Bus queue

**Date:** 2 October 2026 (Asia/Kolkata)
**Status:** Implemented and end-to-end validated on 2 October 2026.

## Objective and architecture

Connect the existing Day 3 Consumption Logic App to the existing Day 2 Flex Consumption Python Function asynchronously by adding one Service Bus Standard namespace and one queue to the existing Central India resource group.

HTTP request → existing Logic App → Logic App UAMI (Data Sender) → Service Bus queue → existing Function (Data Receiver) → existing Function UAMI.

The existing Logic App uses a GET request trigger with no request body. After its Function HTTP action succeeds, it sends a compact event envelope containing the workflow run ID and event type. The Service Bus trigger consumes and completes messages. The payload is not logged. No new compute, identity, storage, connector resource, or monitoring resource is required.

## Readiness and design checkpoint

The repository was on docs/azure-sprint-day-03, based on 0f4c293 and aligned with local main and origin/main. The pre-existing unstaged change in day2-function/function_app.py changes the HTTP route auth level from FUNCTION to ANONYMOUS for the Day 3 managed-identity call. It is preserved in the working tree and is excluded from the Day 4 commit.

Read-only checks confirmed the enabled subscription e5939949-6509-48de-964b-5f1b65c34714, existing Central India resource group rg-ai-azure-integration-lab, Day 2 Function/storage/UAMI, and Day 3 Logic App/UAMI. No Service Bus namespace existed. Microsoft.Web and Microsoft.Logic were registered; Microsoft.ServiceBus was initially NotRegistered and was registered before deployment. The existing monthly cost budget is ₹19,109.25. The usage query returned no actual cost values, so current spend is not asserted. Budget alerts are not a spending cap.

The design checkpoint compared Basic queue, Standard queue, and Standard topic. Basic is cheaper for a queue-only exercise; Standard queue supports the chosen integration and managed identity path; a topic adds fan-out without a second consumer. The user selected Standard queue and authorized proceeding. Standard has a subscription-level base charge plus operation charges. Review live India pricing and the current budget before reproduction; this record does not claim a fixed price.

## Reasoning prompts and checkpoints

The pre-provisioning discussion compared: (1) Standard queue with the existing Logic App and Function using managed identities, (2) Basic queue as the lowest-cost queue-only exercise, and (3) Standard topic for publish/subscribe fan-out. The user confirmed that Basic was cheapest while Standard better demonstrated the chosen integration concepts, selected option 1, and said to proceed. No resource was created before that choice. The key checkpoint was accepting the Standard subscription-level base charge in exchange for the managed-identity path and reuse of existing workloads.
## Concepts and decisions

A queue decouples producer availability from consumer availability. Competing consumers share work; a message is processed by one consumer. A topic would be appropriate if independent subscribers each need a copy.

The Logic App UAMI gets Azure Service Bus Data Sender only at this queue. The Function UAMI gets Azure Service Bus Data Receiver only at this queue. Local/SAS authentication is disabled. The Logic App uses its existing HTTP built-in action with a managed identity token whose audience is https://servicebus.azure.net/. The Function uses identity-based connection settings with its existing UAMI. No connection string or secret is stored.

On successful handler return, the trigger completes the message. Exceptions or invalid UTF-8 cause retries; after maxDeliveryCount 5, the message goes to the dead-letter subqueue. Expiration dead-lettering is enabled. The Function logs message ID, content type, and byte count, never the payload.

Data Receiver is the minimum data-plane role. Microsoft documents that accurate Functions scaling metrics may require Data Owner or a custom namespace read permission. This lab accepts peek-based message count estimation rather than granting Data Owner; production autoscaling needs a separate least-privilege review.

## Infrastructure and reproduction

Run PowerShell from the repository root. The Bicep template derives a globally unique namespace name from the subscription and resource group, sets TLS 1.2 minimum, disables local authentication, enables the public endpoint required by the existing hosted apps, creates one non-session queue, and adds two queue-scoped assignments.

### Register provider and preview

    az account set --subscription e5939949-6509-48de-964b-5f1b65c34714
    az account show --query "{id:id,state:state}" -o json
    az provider show --namespace Microsoft.ServiceBus --query registrationState -o tsv
    az provider register --namespace Microsoft.ServiceBus --wait
    az provider show --namespace Microsoft.ServiceBus --query registrationState -o tsv
    az deployment group what-if --name day4-servicebus --resource-group rg-ai-azure-integration-lab --template-file infra/day4-servicebus.bicep

Review for exactly one Standard namespace, one queue, and two queue-scoped assignments. The template references the existing identities.

### Deploy namespace, queue, and roles

    az deployment group create --name day4-servicebus --resource-group rg-ai-azure-integration-lab --template-file infra/day4-servicebus.bicep --query properties.outputs -o json

    $deployment = az deployment group show --name day4-servicebus --resource-group rg-ai-azure-integration-lab --query properties.outputs -o json | ConvertFrom-Json
    $namespaceName = $deployment.namespaceName.value
    $queueName = $deployment.queueName.value

### Configure and deploy the Function consumer

Function UAMI client ID for this lab: d45e36bc-698a-4cf2-9943-96eea26bd4d4. The app settings contain only namespace and identity selectors:

    az functionapp config appsettings set --name day2fnsprint29 --resource-group rg-ai-azure-integration-lab --settings "ServiceBusConnection__fullyQualifiedNamespace=$namespaceName.servicebus.windows.net" "ServiceBusConnection__credential=managedidentity" "ServiceBusConnection__clientId=d45e36bc-698a-4cf2-9943-96eea26bd4d4"

Package only function_app.py, host.json, and requirements.txt (not .venv, caches, local settings, or editor files), then remote-build for Linux:

    $package = Join-Path $env:TEMP 'day4-servicebus-function.zip'
    Compress-Archive -Path day2-function/function_app.py,day2-function/host.json,day2-function/requirements.txt -DestinationPath $package -Force
    az functionapp deployment source config-zip --name day2fnsprint29 --resource-group rg-ai-azure-integration-lab --src $package --build-remote true --subscription e5939949-6509-48de-964b-5f1b65c34714 --timeout 180000

The Python v2 Service Bus decorator uses the existing extension bundle 4.x. The package carries the existing unstaged auth-level change needed for Day 3, but that change is excluded from the Day 4 Git commit.

### Add the Logic App sender

After RBAC propagation, run the idempotent helper:

    .\scripts\day4\update-logicapp-servicebus.ps1 -NamespaceName $namespaceName -QueueName $queueName

It verifies the signed-in subscription and existing HTTP action, then adds/updates Send_ServiceBus_Message after successful Function invocation. Its JSON body contains workflow().run.name and eventType day4-integration-event because the existing HTTP trigger is GET and has no body. It preserves the other workflow actions, trigger, parameters, identity, and tags. It does not print or save callback URLs. The new action sends JSON to the Service Bus REST endpoint over HTTPS and authenticates with the Logic App UAMI. No API connection resource is created.

## Validation evidence

| Check | Evidence | Meaning |
|---|---|---|
| Subscription/group readiness | Enabled subscription; existing Central India group | Correct target |
| Existing resources | Function and Logic App with existing identities | Reuse |
| Provider readiness | Microsoft.ServiceBus changed from NotRegistered to Registered before deployment | Provider ready |
| Cost guardrail | Budget ₹19,109.25; usage values unavailable | Current spend unverified |
| Bicep compile / preview | Bicep CLI 0.47.16 compiled successfully. Initial what-if planned exactly four additions. The first ARM attempt partially created the namespace, queue, and Sender assignment, then rejected a mistyped Receiver role ID. The ID was corrected from the live subscription role catalog; retry what-if planned only the missing Receiver assignment. | Corrected without duplicating resources |
| Azure deployment | Succeeded. Namespace sb-ai-int-likwmn7js4ffw; queue integration-events; one Logic App Data Sender and one Function Data Receiver assignment, both at queue scope. | Four Day 4 resources provisioned in the existing group |
| Function package/indexing | Zip deployment returned HTTP 202 and completed successfully after remote Linux build and trigger sync. Azure listed BlobIdentityDemo and ServiceBusQueueConsumer. | Python v2 trigger indexed in the existing Function app |
| Local CI gate | Ruff 0.16.10 passed; pytest 6 passed; coverage 100% (required 85%). Python 3.14.4. | Existing quality check passed |
| Logic App → queue → Function | Trigger returned HTTP 202; run Succeeded; HTTP and Send_ServiceBus_Message succeeded; failure Scope was skipped. Application Insights recorded the payload-free consumer trace at 2026-10-01 23:03:20Z (content type application/json, 84 bytes). Queue count after processing: 0 active, 0 dead-letter; configured max delivery count 5. | End-to-end path verified |
| Dead-letter path | Not deliberately forced | Queue has max delivery count 5 and expiration dead-lettering; no poison message was injected |

Reproduce the happy path with .\scripts\day4\invoke-day4-smoke-test.ps1. It retrieves the HTTP trigger callback in memory, makes a GET request (the existing trigger method), and prints only status codes. Never commit or print the callback URL, access keys, Function keys, tokens, or message bodies.

## Security and cost

- Namespace local/SAS auth disabled; no shared key used.
- Sender and Receiver roles are separate and queue-scoped.
- Function settings contain identifiers, not secrets.
- Public endpoint is used because the current Consumption Logic App and Function have no private VNet path. HTTPS and TLS 1.2 are enforced.
- Standard has a recurring subscription-level base charge while provisioned plus message operation charges. Check [Service Bus India pricing](https://azure.microsoft.com/en-in/pricing/details/service-bus/) and the subscription budget. Alerts notify; they do not cap spending.
- No diagnostic setting, new compute, storage, or identity is added.

## Cleanup and rollback

Do not delete the shared resource group. First remove the Logic App sender action, then disable the Function trigger before removing its connection settings. Delete the scoped roles and only the Day 4 namespace (which removes its queue). These commands are for eventual cleanup, not executed during this lab:

    .\scripts\day4\update-logicapp-servicebus.ps1 -RemoveSenderAction
    az functionapp config appsettings set --name day2fnsprint29 --resource-group rg-ai-azure-integration-lab --settings AzureWebJobs.ServiceBusQueueConsumer.Disabled=true
    az functionapp config appsettings delete --name day2fnsprint29 --resource-group rg-ai-azure-integration-lab --setting-names ServiceBusConnection__fullyQualifiedNamespace ServiceBusConnection__credential ServiceBusConnection__clientId
    $queueId = '/subscriptions/e5939949-6509-48de-964b-5f1b65c34714/resourceGroups/rg-ai-azure-integration-lab/providers/Microsoft.ServiceBus/namespaces/sb-ai-int-likwmn7js4ffw/queues/integration-events'
    az role assignment delete --assignee 9ab0f1a5-7d68-46b6-8431-8e861d9de833 --role 69a216fc-b8fb-44d8-bc22-1f3c2cd27a39 --scope $queueId
    az role assignment delete --assignee 9fadac85-168d-4032-827f-ff98fb8b2410 --role 4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0 --scope $queueId
    az resource delete --ids /subscriptions/e5939949-6509-48de-964b-5f1b65c34714/resourceGroups/rg-ai-azure-integration-lab/providers/Microsoft.ServiceBus/namespaces/sb-ai-int-likwmn7js4ffw --api-version 2024-01-01

Keep the Function code deployed but disabled if you intend to recreate the namespace, or remove the trigger code in a reviewed code update. Verify that the namespace and assignments are gone and no Function setting points to the deleted namespace. Leave Microsoft.ServiceBus registered; provider registration itself has no per-resource running charge.

## Troubleshooting checkpoints

- Provider error: wait for provider registration and confirm Registered.
- 401/403 send: verify Logic App UAMI, exact audience (trailing slash), and Sender assignment at queue scope.
- RBAC first-use failure: allow several minutes for role assignment propagation.
- Function cannot connect: inspect identity-based setting names, UAMI client ID, queue name, Receiver scope, extension bundle, and host logs. Do not switch to a connection string.
- Missing trigger: verify remote build, deployment response, host sync, and extension indexing.
- Scaling estimate: Data Receiver lacks Service Bus management/read; the lab accepts the less precise peek-count fallback.
- Dead-letter: inspect error and delivery count; fix the handler before controlled replay.

## Interview takeaways

- Queues decouple systems and use competing consumers; topics provide independent fan-out.
- Delivery is at least once, so handlers should be idempotent.
- Dead-letter queues isolate repeatedly failing/expired messages and need a controlled monitor/replay process.
- Managed identity removes credential rotation; narrow RBAC separates sender and receiver.
- Standard capability must justify its subscription-level base charge.
- A successful send and successful consumer processing are separate validation checkpoints.

## Tools and technology

- Azure CLI: account/resource/provider inspection, what-if/deployment, Function configuration, package deployment, ARM REST calls; Bicep CLI 0.47.16 was available through az bicep.
- Bicep: namespace, queue, deterministic role assignments.
- Azure Service Bus Standard: durable queue, message locks, retry and dead-letter behavior.
- Logic Apps Consumption: existing workflow and HTTP managed-identity action.
- Azure Functions Flex Consumption/Python v2: existing Function with Service Bus trigger; existing extension bundle supplies binding.
- Entra managed identities and Azure RBAC: no shared keys; separate queue-scope permissions.
- PowerShell: idempotent workflow patch and smoke-test helper; callback URL stays in memory.
- Git/GitHub: Day 4 branch/PR and quality gate; unrelated local Day 2 edit is not staged or committed.
- Existing Application Insights can show Function traces; no extra Monitor resource is required.

## Sources

- [Service Bus RBAC and managed identities](https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-managed-service-identity)
- [Logic Apps managed identity authentication](https://learn.microsoft.com/en-us/azure/logic-apps/authenticate-with-managed-identity)
- [Azure Functions Service Bus trigger](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-service-bus-trigger)
- [Service Bus REST send message](https://learn.microsoft.com/en-us/rest/api/servicebus/send-message-to-queue)
- [Service Bus pricing](https://azure.microsoft.com/en-in/pricing/details/service-bus/)

## Next-lab dependency

Day 5 can build on retries, poison-message handling, and a deliberate dead-letter inspection/replay exercise. Retain the queue until that lab or remove the Standard namespace if cost minimization takes priority.
