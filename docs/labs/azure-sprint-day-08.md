# Azure sprint — Day 8: Dead-letter queue inspection and replay tooling

## Objectives & Architecture

Day 8 establishes an attended operator CLI workflow (`scripts/day8/dlq_manager.py` and `scripts/day8/seed_dlq.py`) for safely inspecting, remediating, and replaying dead-lettered messages in Azure Service Bus (`integration-events/$DeadLetterQueue`).

```text
                      [Service Bus Queue: integration-events]
                                          |
                                          v (delivery failure x5 / MaxDeliveryCountExceeded)
                                  [$DeadLetterQueue]
                                          |
                +-------------------------+-------------------------+
                v                                                   v
        [dlq_manager.py peek]                               [dlq_manager.py replay]
 (Non-destructive peek_messages)                     (receive_messages, max_wait_time=5)
  - Inspects headers & payload                        - Receives message with peek-lock
  - Audits DeadLetterReason / ErrorDescription        - Decodes byte keys/values while preserving
  - No lock acquired, delivery count unchanged          native application_properties types
                                                      - If --remediate: patches simulate_poison=False
                                                        and sets remediated=True (fails closed if
                                                        JSON is invalid or flag is absent)
                                                      - Preserves message_id, correlation_id,
                                                        content_type, and W3C traceparent
                                                      - Increments x-opt-replay-attempt and records
                                                        x-original-deadletter-reason
                                                      - Step 1: sender.send_messages(replayed_msg)
                                                      - Step 2: receiver.complete_message(msg)
```

### Core Design Decisions

1. **Attended CLI Operations:** DLQ inspection and replay are implemented as standalone CLI utilities (`scripts/day8/dlq_manager.py` and `scripts/day8/seed_dlq.py`) using `DefaultAzureCredential` (no SAS keys). The Azure Function consumer (`day2-function/function_app.py`) remains unchanged.
2. **Trace & Metadata Continuity:** Replayed messages preserve `message_id`, `correlation_id`, `content_type`, and existing `application_properties` (decoding AMQP `bytes` keys/values while preserving native `int`, `bool`, `float`, and `str` types, including W3C `traceparent`), while stamping `x-opt-replay-attempt` (incremented integer string) and `x-original-deadletter-reason`.
3. **Fail-Closed Payload Sanitization (`--remediate`):** In `day2-function/function_app.py`, `service_bus_queue_consumer` raises a `ValueError` when `payload.get("simulate_poison") is True`. When `dlq_manager.py replay --remediate` is invoked, JSON payloads with `"simulate_poison": true` are updated to `"simulate_poison": false` and `"remediated": true` before re-enqueueing. If JSON parsing fails or the payload does not contain an active `simulate_poison` flag, remediation fails closed and leaves the message untouched in `$DeadLetterQueue`.
4. **Send-Then-Complete Ordering & Idempotency Trade-offs:** Replay sends the new message to the active queue before completing the dead-lettered message. If a fault occurs after `send_messages()` but before `complete_message()`, the DLQ lock expires and a subsequent replay will emit a duplicate message with the same `message_id`.

---

## Configuration & Environment Variables

| Component | Environment Variable | Default / Binding | Purpose |
| :--- | :--- | :--- | :--- |
| `scripts/day8/dlq_manager.py`<br>`scripts/day8/seed_dlq.py` | `SERVICE_BUS_FQDN` | `sb-ai-int-likwmn7js4ffw.servicebus.windows.net` | Target Service Bus namespace FQDN for `ServiceBusClient` |
| `scripts/day8/dlq_manager.py`<br>`scripts/day8/seed_dlq.py` | `SERVICE_BUS_QUEUE_NAME` | `integration-events` | Target Service Bus queue name |
| `day2-function/function_app.py` | `SERVICE_BUS_CONNECTION` (`__fullyQualifiedNamespace` in Azure) | Configured in Function App settings | Azure Functions Service Bus trigger connection prefix |

### Required Azure RBAC Roles (Operator Identity)
* **Azure Service Bus Data Receiver:** Required to peek and receive/complete messages from `integration-events/$DeadLetterQueue`.
* **Azure Service Bus Data Sender:** Required to seed test messages and send replayed messages back to `integration-events`.

---

## Replay Message Transformation Contract

| Property / Field | Replay Behavior | Notes |
| :--- | :--- | :--- |
| `message_id` | Preserved (`msg.message_id`) | Used by consumer idempotency check (`PROCESSED_MESSAGE_IDS`) |
| `correlation_id` | Preserved (`msg.correlation_id`) | Retains application-level correlation context |
| `content_type` | Preserved (`msg.content_type`) | Preserves MIME type (e.g., `application/json`) |
| `application_properties` | Preserved (UTF-8 `bytes` decoded; `int`, `bool`, `float`, `str` types preserved) | Maintains W3C `traceparent` and typed custom headers |
| `application_properties["x-opt-replay-attempt"]` | Added / Incremented (`"1"`, `"2"`, ...) | Tracks how many times the message has been replayed |
| `application_properties["x-original-deadletter-reason"]` | Added (`msg.dead_letter_reason` or `"MaxDeliveryCountExceeded"`) | Preserves why the message was dead-lettered |
| JSON Body (`simulate_poison`) | Unchanged by default; set to `False` with `"remediated": True` when `--remediate` is passed | Fails closed (leaves message in DLQ) if JSON parsing fails or active flag is missing |

---

## Executed Validation (Local Unit Tests & Linting)

The following checks were executed locally against the repository test suite (using mocked `ServiceBusClient` receivers and senders; no live Azure runtime claim is made here):

```powershell
# 1. Static analysis & import/style checks
ruff check scripts/day8 tests

# 2. Unit test suite & coverage for scripts/day8
python -m pytest tests/test_dlq_manager.py -v --cov=scripts.day8 --cov-report=term-missing
```

### Verified Test Cases (`tests/test_dlq_manager.py`)
* `test_peek_dlq_empty`: Verifies `peek_messages(max_message_count=5)` is called once and reports an empty DLQ.
* `test_peek_dlq_with_messages`: Verifies non-destructive inspection output and UTF-8 decoding of byte-encoded `traceparent` headers.
* `test_replay_dlq_remediate_flag`: Verifies `receive_messages(max_message_count=1, max_wait_time=5)` is called once, `simulate_poison` is remediated to `False` with `remediated: True`, `message_id`, `correlation_id`, `content_type`, `traceparent`, and native property types (`int`, `bool`) are preserved, `x-opt-replay-attempt` increments from `"1"` to `"2"`, `x-original-deadletter-reason` is recorded, and `sender.send_messages()` executes before `receiver.complete_message()`.
* `test_replay_dlq_remediate_invalid_json_fails_closed`: Verifies malformed JSON payloads are neither re-sent nor completed when `--remediate` is specified.
* `test_replay_dlq_remediate_missing_poison_flag_fails_closed`: Verifies payloads lacking an active `simulate_poison` flag are neither re-sent nor completed when `--remediate` is specified.

---

## Live Azure Reproduction Runbook

To execute the end-to-end poison seeding, DLQ inspection, and remediation replay flow against the live Azure Service Bus namespace:

```powershell
# 1. Authenticate with Azure CLI and configure environment variables
az login
$env:SERVICE_BUS_FQDN = "sb-ai-int-likwmn7js4ffw.servicebus.windows.net"
$env:SERVICE_BUS_QUEUE_NAME = "integration-events"

# 2. Seed a synthetic poison message (simulate_poison=True)
python scripts/day8/seed_dlq.py

# 3. Wait for the Function consumer to exhaust MaxDeliveryCount (5 attempts), then peek DLQ
python scripts/day8/dlq_manager.py peek --count 5

# 4. Replay from DLQ with payload remediation enabled
python scripts/day8/dlq_manager.py replay --count 5 --remediate

# 5. Confirm DLQ is empty after replay
python scripts/day8/dlq_manager.py peek --count 5
```

---

## Operational Risks & Limitations

1. **No Automatic Replay Cap in CLI:** `dlq_manager.py` increments `x-opt-replay-attempt` on each replay but does not enforce a maximum replay threshold. Replaying a poison message without fixing the underlying defect (or without `--remediate` for simulated poison messages) will cause the consumer to fail 5 more times and return the message to `$DeadLetterQueue`.
2. **Send-Then-Complete Duplicate Window:** If `sender.send_messages(replayed_msg)` succeeds but `receiver.complete_message(msg)` fails (e.g., network drop or process termination), the message remains in `$DeadLetterQueue` while a copy is already enqueued on `integration-events`.
3. **In-Memory Consumer Idempotency Limitations:** `day2-function/function_app.py` tracks processed IDs in an in-memory module-level set (`PROCESSED_MESSAGE_IDS`) and only adds `message_id` after processing succeeds. While a message that previously failed every delivery attempt will not be in `PROCESSED_MESSAGE_IDS` on its first successful replay, duplicate deliveries caused by a send-then-complete crash are only deduplicated if they land on the **same warm Function worker instance** before a process restart or scale-in/scale-out event.
