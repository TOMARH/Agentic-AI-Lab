# Azure Sprint Day 6: Consumer Idempotency & Dead-Letter Queue Handling

## Overview
Day 6 focuses on resilient queue consumption patterns, idempotency handling under at-least-once delivery semantics, and dead-letter subqueue (DLQ) operations for poison messages.

## Key Changes
- **Function App:** Updated `ServiceBusQueueConsumer` in `day2-function/function_app.py` with message ID deduplication and structured poison-message validation.
- **Test Suite:** Added unit test coverage for duplicate skipping, simulated poison message handling, and malformed payload detection (9/9 tests passing).
- **Tooling:** Implemented `scripts/day6/inspect-dlq.ps1` for real-time queue depth and DLQ monitoring.
- **ADR:** Added `docs/adr/0006-consumer-idempotency-and-dead-letter-management.md`.

## Verification
- Unit test suite: `python -m pytest day2-function/tests -v` (9 passed).
- Queue diagnostics: Verified live Azure Service Bus queue `integration-events` in namespace `sb-ai-int-likwmn7js4ffw`.