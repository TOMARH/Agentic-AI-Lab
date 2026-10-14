# ADR 0007: Publish typed decision events to the existing Service Bus queue

- **Status:** Accepted for Day 10
- **Date:** 14 October 2026
- **Decision owners:** User and architecture workflow

## Context

Day 9 introduced a local rules-first decision model. Its `Decision` result records topic, recommendation, source (`rule`, `llm`, or `unmatched`), and rationale. The integration exercise needs to carry that provenance into the existing Azure messaging flow without provisioning another namespace or changing the established Function consumer.

The existing `integration-events` queue accepts JSON messages. Its Function consumer parses valid JSON, logs message metadata rather than the body, and handles delivery failures and dead-lettering as previously documented in ADR 0006.

## Decision

Add an operator-invoked local producer that serializes a decision into a versioned `ArchitectureDecision.Created` JSON envelope and sends it to the existing `integration-events` queue. Authenticate with `DefaultAzureCredential` and the existing queue-scoped Azure Service Bus Data Sender assignment. Preserve the Day 9 decision source and rationale in the event body, and include machine-readable `advisory: true` in the envelope for every source. Use the Service Bus message ID for the event ID, W3C-formatted correlation headers (`traceparent` and `Diagnostic-Id`, validated to reject malformed or all-zero IDs) in application properties, and JSON content type. Because the CLI does not initialize an OpenTelemetry tracer or export producer spans, these headers provide message-level correlation context rather than exported end-to-end distributed traces.

Do not change the consumer, queue, namespace, identities, role assignments, or infrastructure. Every event is explicitly advisory; this producer does not execute a recommendation or convert it into authorization or policy.

## Alternatives considered

1. **Create a new namespace/queue:** rejected because the existing queue has the required generic JSON contract and sender access; another namespace would add avoidable recurring cost and operational surface.
2. **Change the Function consumer to execute decisions:** rejected because this lab is about message integration and provenance, not introducing model output into production policy or adding a new consumer behavior.
3. **Put the decision fields only in AMQP application properties:** rejected because the complete decision is a business event payload; properties are reserved for transport metadata and correlation context.

## Consequences

- Day 9 provenance travels with the event and survives asynchronous decoupling.
- Schema versioning permits future consumers to evolve deliberately.
- The existing generic JSON consumer accepted the smoke-test message without a code or deployment change; see the correlated trace evidence in the Day 10 lab. This observation does not establish compatibility for future schema changes.
- Every envelope is marked `advisory: true`, so consumers can reject attempts to treat a decision event as authorization or an executable command.
- The Standard tier includes the first 13 million messaging operations each month; the smoke test used one send operation, but total subscription usage against that allowance was not verified. The existing Standard namespace's base charge continues. No new Azure resource is added.
- The queue remains at-least-once. Duplicate detection is disabled on the existing queue. A retry after an ambiguous send timeout can therefore enqueue a duplicate even when the retry reuses the same event ID. Consumers still need idempotent handling; the existing Function's in-memory set is not a durable business-level dedupe store.
- Confidential topics and model suggestions must not be sent unless provider and organizational data-handling rules permit them.

## References

- [Day 9 local decision model](../labs/azure-sprint-day-09.md)
- [Day 10 decision event integration](../labs/azure-sprint-day-10.md)
- [ADR 0006: Consumer idempotency and dead-letter management](0006-consumer-idempotency-and-dead-letter-management.md)
