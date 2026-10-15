# Azure sprint — Day 13: Consumer duplicate-delivery behavior

## Objective

Exercise the existing Service Bus consumer's duplicate-delivery behavior with local unit tests. The tests use a fake message and the module-level `PROCESSED_MESSAGE_IDS` set; they do not connect to Azure or prove broker behavior.

## Consumer contract

The consumer checks `message.message_id` before reading the body. After a message is handled successfully, its ID is added to `PROCESSED_MESSAGE_IDS`; a later invocation with that ID is skipped without reading the body again. If decoding, JSON parsing, or simulated poison handling fails, the ID is not recorded, so a later delivery with the same ID can be processed.

The focused tests in `day2-function/tests/test_function_app.py` cover successful duplicate suppression and the failure-then-retry sequence: a failed delivery is not marked processed, the successful retry is recorded, and another delivery is skipped.

## Process-local limitation

`PROCESSED_MESSAGE_IDS` is an in-memory Python set. It lasts only for the lifetime of one worker process, is not shared across Function workers, and is lost when a worker restarts or scales in. The same message can therefore be processed again by another worker or after a restart. The set also has no expiry or durable retention policy. This is a best-effort local guard, not durable idempotency and not an exactly-once guarantee.

For production side effects that must not repeat, use a durable idempotency record or business constraint keyed by message ID, with atomic coordination between recording the key and applying the side effect. A shared cache or database can provide cross-worker state, but the application must still define retention and failure semantics. Service Bus duplicate detection, when configured, is a separate broker-side feature and does not make consumer side effects exactly once.

## Validation scope

All checks described for this day are local and deterministic. No Azure resources, live queues, or consumer implementation changes are part of this lab.
