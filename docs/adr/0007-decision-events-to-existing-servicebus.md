# ADR 0007: Publish typed decision events to the existing Service Bus queue

- **Status:** Accepted for Day 10
- **Date:** 14 October 2026
- **Decision owners:** User and architecture workflow

## Context

Day 9 introduced a local rules-first decision model. Its `Decision` result records topic, recommendation, source (`rule`, `llm`, or `unmatched`), and rationale. The integration exercise needs to carry that provenance into the existing Azure messaging flow without provisioning another namespace or changing the established Function consumer.

The existing `integration-events` queue accepts JSON messages. Its Function consumer parses valid JSON, logs message metadata rather than the body, and handles delivery failures and dead-lettering as previously documented in ADR 0006.

## Decision

Add an operator-invoked local producer that serializes a decision into a versioned `ArchitectureDecision.Created` JSON envelope and sends it to the existing `integration-events` queue. Authenticate with `DefaultAzureCredential` and the existing queue-scoped Azure Service Bus Data Sender assignment. Preserve the Day 9 decision source and rationale in the event body. Use the Service Bus message ID for the event ID, a W3C `traceparent` in application properties, and JSON content type.

Do not change the consumer, queue, namespace, identities, role assignments, or infrastructure. A model-generated recommendation remains advisory data; this producer does not execute it or convert it into authorization or policy.

## Alternatives considered

1. **Create a new namespace/queue:** rejected because the existing queue has the required generic JSON contract and sender access; another namespace would add avoidable recurring cost and operational surface.
2. **Change the Function consumer to execute decisions:** rejected because this lab is about message integration and provenance, not introducing model output into production policy or adding a new consumer behavior.
3. **Put the decision fields only in AMQP application properties:** rejected because the complete decision is a business event payload; properties are reserved for transport metadata and trace context.

## Consequences

- Day 9 provenance travels with the event and survives asynchronous decoupling.
- Schema versioning permits future consumers to evolve deliberately.
- The existing consumer can accept the message without a code or deployment change.
- A single send incurs normal Service Bus operation usage; the existing Standard namespace's recurring charge continues. No new Azure resource is added.
- The queue remains at-least-once. The event ID is useful for downstream deduplication, but the existing Function's in-memory idempotency set is not a durable business-level dedupe store.
- Confidential topics and model suggestions must not be sent unless provider and organizational data-handling rules permit them.

## References

- [Day 9 local decision model](../labs/azure-sprint-day-09.md)
- [Day 10 decision event integration](../labs/azure-sprint-day-10.md)
- [ADR 0006: Consumer idempotency and dead-letter management](0006-consumer-idempotency-and-dead-letter-management.md)
