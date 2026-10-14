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

---

## Addendum (Day 8): Controlled DLQ Replay Contract

### Decision
1. **Replay Envelope Preservation:** Attended operator replay tooling (`scripts/day8/dlq_manager.py`) constructs a new `ServiceBusMessage` preserving `message_id`, `correlation_id`, `content_type`, and `application_properties`, preserving typed values and decoding known text headers such as W3C `traceparent`, while stamping `x-opt-replay-attempt` (incremented per replay) and `x-original-deadletter-reason`.
2. **Send-Then-Complete Ordering:** During replay, `sender.send_messages()` executes before `receiver.complete_message()` on `$DeadLetterQueue` to favor possible duplicate delivery over message loss; duplicates remain possible if completion fails.

### Operational Trade-offs & Idempotency Scope
- **Duplicate-Delivery Window:** If `send_messages()` succeeds but `complete_message()` fails, the message is enqueued to `integration-events` while remaining in `$DeadLetterQueue`, creating a duplicate delivery when re-processed.
- **In-Memory Idempotency Limitation:** `ServiceBusQueueConsumer` (`day2-function/function_app.py`) records `message_id` in `PROCESSED_MESSAGE_IDS` only after successful execution, and that set resides in worker memory. Therefore, a poison message that failed all 5 prior attempts will execute normally on its first remediated replay, but any duplicate delivery resulting from an interrupted `complete_message()` call is only deduplicated if routed to the same warm worker instance.
