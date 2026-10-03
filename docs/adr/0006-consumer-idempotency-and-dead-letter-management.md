# 6. Consumer Idempotency and Dead-Letter Management

Date: 2026-10-03

## Status

Accepted

## Context

The architecture buffers asynchronous events from Logic Apps (Day 4) and Event Grid Storage notifications (Day 5) through an Azure Service Bus queue (`integration-events`). 

In distributed systems, Service Bus guarantees at-least-once delivery. Consequently:
1. Network retries, consumer restarts, or lock renewal timeouts can deliver duplicate messages to the Python consumer.
2. Malformed messages or persistent domain errors can cause infinite retry loops, exhausting worker resources.

## Decision

1. **Consumer Idempotency:** The Python `ServiceBusQueueConsumer` tracks unique message IDs (`message.message_id`). Incoming duplicate deliveries are identified, logged as warnings, and cleanly skipped without re-executing business logic.
2. **Controlled Dead-Lettering (Poison Messages):** Unprocessable or corrupt messages (e.g. invalid UTF-8, malformed JSON, or explicit domain errors) trigger unhandled exceptions. Azure Service Bus manages delivery counts against the configured `MaxDeliveryCount` (5). Upon exhaustion, the broker routes the message to the dead-letter subqueue (`integration-events/$DeadLetterQueue`) with `DeadLetterReason: MaxDeliveryCountExceeded`.
3. **Operational Observability:** DLQ metrics and messages are inspected using dedicated tooling (`scripts/day6/inspect-dlq.ps1`) without requiring destructive message consumption during diagnostic triage.

## Consequences

- **Positive:** Duplicate message processing is avoided; poison messages cannot block active queue throughput.
- **Negative / Trade-off:** In-memory deduplication is scoped per worker instance. For high-scale multi-instance production deployments, deduplication state should be backed by an external cache (e.g., Azure Cache for Redis or Azure Cosmos DB) or Service Bus native duplicate detection within the detection window.