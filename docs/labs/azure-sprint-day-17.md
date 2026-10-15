# Azure sprint — Day 17: Offline retry and duplicate reliability contract

## Objective and evidence

Exercise the failure boundary between JSON decoding and the existing in-memory policy-gate deduplication. The test in `tests/test_day15_offline_boundary.py` submits malformed JSON with a caller-owned `seen_event_ids` set, verifies that the decoding exception propagates without recording an ID, then submits a valid serialized publisher event and verifies it is evaluated. A subsequent delivery of that same event is classified as a duplicate.

This establishes the local contract needed for an adapter to let malformed input fail and remain eligible for its configured retry handling, while ensuring parse failure does not poison process-local deduplication state. It does not exercise an Azure Function binding, Service Bus settlement, retry count, DLQ routing, concurrent workers, process restart, or durable idempotency.

## Scope and limitations

The change is offline-only and reuses the Day 15 serialized boundary. No publisher, Function consumer, broker, Azure resource, or live message was changed or exercised. The in-memory set remains process-local and non-atomic; no exactly-once or production reliability guarantee is claimed.
