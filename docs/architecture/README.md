# Architecture

## Current Azure integration flow

    Logic App (Day 3)
       | managed identity
       v
    Service Bus queue (Day 4) <-- Event Grid Storage system topic (Day 5)
       |                                  ^
       |                                  | BlobCreated in incoming
       v                                  |
    Python Function consumer       Existing Storage account

    Day 10 local decision publisher
       | Entra ID / queue-scoped Data Sender
       +-------------------------------------> existing Service Bus queue

The Logic App and Event Grid are independent producers for the same queue. The Day 10 local CLI can also publish a versioned architecture-decision event to that queue, using the existing Entra ID role assignment. The Function consumer stays decoupled from all producers. Event Grid filters notifications; Service Bus durably buffers work.

## Architecture principles

- Reuse existing resources before provisioning duplicates.
- Use managed identity and narrow Azure RBAC scopes.
- Keep event notification distinct from durable work processing.
- Treat event and queue delivery as at-least-once; design idempotent consumers.
- Record retry, dead-letter, monitoring, cost, and lifecycle decisions with each integration lab.

For implementation and evidence, see the [Day 4 Service Bus lab](../labs/azure-sprint-day-04.md) and [Day 5 Event Grid lab](../labs/azure-sprint-day-05.md).
The Day 10 [decision event lab](../labs/azure-sprint-day-10.md) reuses the existing namespace and queue.
