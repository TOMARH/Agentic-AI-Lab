# Azure Sprint — Day 12: Dead-Letter Replay Failure Semantics

## Objective

Exercise the failure boundaries in the existing Service Bus dead-letter queue (DLQ) replay utility. Keep this work local and deterministic; do not provision Azure resources or perform live Service Bus operations.

## Existing replay contract

The existing `scripts/day8/dlq_manager.py` replay flow:

1. Receives messages from the DLQ.
2. Optionally validates and remediates the simulated poison flag.
3. Creates a replay message while preserving message identity, correlation, content type, and application properties.
4. Sends the replay message to the active queue.
5. Completes the original DLQ message only after the send call returns successfully.

## Failure-path tests

Two tests were added to `tests/test_dlq_manager.py`:

- `test_replay_dlq_send_failure_does_not_complete_original`: a simulated send failure propagates, and the original DLQ message is not completed.
- `test_replay_dlq_completion_failure_surfaces_after_send`: a simulated completion failure propagates after one send attempt and one completion attempt.

These are mocked unit tests. They verify local control flow, not actual broker behavior.

## Reliability implications

Send and completion are separate operations; they are not an atomic transaction in this implementation.

If the broker accepts the replay but the client encounters an ambiguous result, or if sending succeeds and completing the original fails, the original may remain available for another replay. A later replay can therefore create a duplicate.

Preserving `message_id` does not by itself establish duplicate prevention. The current lab notes indicate that Service Bus duplicate detection is disabled. Do not claim exactly-once delivery.

No automatic retry was added. Retrying a send after an ambiguous outcome may create another copy. Safer recovery requires an explicit deduplication, idempotency, or reconciliation design appropriate to the consumer and broker configuration.

## Validation evidence

- Baseline before adding the tests: 5 DLQ manager tests passed.
- After adding the two failure-path tests: 7 DLQ manager tests passed.
- Targeted Ruff checks for `tests/test_dlq_manager.py` and `scripts/day8/dlq_manager.py` passed.
- `git diff --check` reported no whitespace errors after removing the extra blank line; Git emitted a line-ending conversion warning.

Run the full repository suite and final checks before treating Day 12 as complete.

## Scope and limitations

- No production code changed as part of the failure-path test addition.
- No live Service Bus calls or Azure resource changes were performed.
- Mocked failures do not establish the behavior of the broker under network partitions, lock expiry, or ambiguous send outcomes.
