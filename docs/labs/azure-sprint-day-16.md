# Azure sprint — Day 16: Offline reliability and idempotency design

## Objective and scope

Translate the Day 10 publisher, Day 2 Service Bus Function, Day 11 policy gate, and Day 15 serialized boundary into an offline reliability contract. This is a design artifact and deterministic test coverage only. It changes no consumer, broker, Azure resource, or storage behavior and does not claim durable idempotency.

## Current delivery and identity contract

- Service Bus delivery is at least once. The Function binding owns settlement: a normal function return is eligible for completion; an uncaught decode, JSON, or poison error remains eligible for retry and eventual dead-lettering under the queue's configured delivery policy. These local tests model exceptions and function returns, not broker settlement.
- Day 10 sets `ServiceBusMessage.message_id` equal to the body `eventId`. The Day 2 consumer currently deduplicates by `message.message_id`; Day 11/15 deduplicate by the validated body `eventId`. They coincide for publisher-built events, but arbitrary producers can make them differ. A future integrated consumer must reject a mismatch or explicitly select one canonical key; silently mixing them can defeat deduplication.
- IDs identify a logical event only when they are stable across producer retries. A new call to `build_decision_event` without an explicit `event_id` generates a new UUID. Retrying a logical publication by rebuilding can therefore create a distinct identity. Persist/reuse the ID at the producer boundary if retries must represent the same event.
- Current state is process-local: `PROCESSED_MESSAGE_IDS` in the Function and the optional `seen_event_ids` set in the offline policy gate. Neither is shared across workers, survives process restart, expires, nor provides atomic check-and-record across concurrent invocations. The policy gate's check/add is two operations; concurrent calls can both pass.
- Day 15 returns a sanitized audit value to its caller but persists nothing. The current Service Bus consumer logs metadata and has no business side effect or audit ledger. A log line is not a durable audit record.

## Failure windows

| Window | Current observable result | Design implication |
| --- | --- | --- |
| Publisher send is rejected before broker acceptance | Send raises; no successful publish is established | Retry policy must reuse the same logical event ID to avoid a new identity on each attempt. |
| Broker accepts send but producer loses the response | Acceptance is ambiguous; retry may enqueue another delivery | Same message ID helps identify duplicates, but queue duplicate detection is currently disabled and consumer memory is not durable. |
| Consumer decode, JSON parse, or poison handling fails before it records the ID | Exception propagates; local tests show ID absent | Retry can process again; repeated failure can reach the DLQ. |
| Consumer handles message, then worker fails before in-memory ID add | The side effect (if one is later added) may repeat on retry | The check/effect/record sequence needs a durable atomic boundary for non-repeatable work. |
| Consumer adds ID and then worker/binding fails before settlement completes | Redelivery may be skipped only by that still-live worker | A restart or another worker loses that protection; current sample performs no domain side effect. |
| Two workers or concurrent invocations receive the same ID | Each has independent state; both can process | A process-local set cannot coordinate this race. |
| DLQ replay sends successfully but completing the original DLQ message fails | Both original and replay can exist | Replay favors no loss over no duplicates; preserve the logical ID and make the consumer durable/idempotent. |
| Audit is returned/logged but not durably committed | A crash can leave no queryable audit trail | Durable audit requires an explicit sink and a commit protocol; current code has neither. |

## Requirements before claiming durable idempotency

1. Define the canonical key and scope, preferably a validated, immutable `eventId` unique within a documented producer/tenant namespace; reject an envelope when the broker `message_id` conflicts with that key.
2. Persist a unique key with the sanitized outcome, reason code, policy version, and processing timestamp. Define retention, replay, privacy, and policy-version behavior.
3. Atomically claim the key and commit the audit plus any business effect. Use a database uniqueness constraint/transaction, or an inbox/outbox design appropriate to the effect. A separate “check then write” cache lookup is still racy; recording before the effect can lose work, and recording after it can repeat work.
4. On an already committed key, return the prior outcome without repeating the effect. On transient storage failure, fail the invocation so transport retry remains possible. Define how permanent invalid input is audited and routed to DLQ.
5. Validate cross-worker concurrency, restart recovery, ambiguous send/settlement, retention expiry, and DLQ replay against the chosen durable store and real broker before making operational guarantees.

## Offline validation

Day 15 tests now also serialize an LLM-sourced publisher event across the same boundary and verify it stays non-actionable with no recommendation or rationale leakage. This validates the existing policy decision; it does not exercise transport behavior or implement an audit store.
