# Day 8: Service Bus DLQ Inspection & Controlled Replay Tooling

Operator CLI utilities for seeding synthetic poison messages, non-destructively inspecting `$DeadLetterQueue`, and replaying dead-lettered messages back to the active Azure Service Bus queue.

---

## 1. Architecture

```text
+-----------------------------------------------------------------------------------------+
|                                    Azure Service Bus                                    |
|                                                                                         |
|   +--------------------+      Delivery Attempts >= 5        +-------------------------+ |
|   | integration-events | ---------------------------------> |    $DeadLetterQueue     | |
|   +--------------------+                                    +-------------------------+ |
|             ^                                                            |              |
|             |                 scripts/day8/dlq_manager.py                |              |
|             +------------------------------------------------------------+              |
|                              (Replay + Metadata Preservation)                           |
+-----------------------------------------------------------------------------------------+
              |
              v
+-----------------------+
|  Azure Functions      |
|  day2-function        |
|  (Flex Consumption)   |
|                       |
|  Identity: Managed ID |
|  RBAC: Data Receiver  |
+-----------------------+
```

### Security & Configuration
- **Authentication:** Uses `DefaultAzureCredential` (`azure-identity`). SAS connection strings and local keys are not used.
- **Required RBAC Roles:**
  - `Azure Service Bus Data Receiver` (peek and receive/complete on `$DeadLetterQueue`)
  - `Azure Service Bus Data Sender` (seed poison messages and send replayed messages to active queue)
- **Environment Variables:**
  - `SERVICE_BUS_FQDN` (default: `sb-ai-int-likwmn7js4ffw.servicebus.windows.net`)
  - `SERVICE_BUS_QUEUE_NAME` (default: `integration-events`)

---

## 2. CLI Tooling Usage

### A. Seed a Synthetic Poison Message (`seed_dlq.py`)
Sends a JSON event containing `"simulate_poison": true` and a W3C `traceparent` header to `integration-events`. The consumer (`day2-function/function_app.py`) raises a `ValueError` when `payload.get("simulate_poison") is True`, exhausting `MaxDeliveryCount` (5) and routing the message to `$DeadLetterQueue`.

```powershell
$env:SERVICE_BUS_FQDN = "sb-ai-int-likwmn7js4ffw.servicebus.windows.net"
$env:SERVICE_BUS_QUEUE_NAME = "integration-events"
python scripts/day8/seed_dlq.py
```

### B. Non-Destructive DLQ Inspection (`dlq_manager.py peek`)
Peeks up to `--count` messages (default `5` via CLI) from `$DeadLetterQueue` without acquiring locks or altering delivery counts:

```powershell
python scripts/day8/dlq_manager.py peek --count 5
```

### C. Controlled DLQ Replay (`dlq_manager.py replay`)
Receives up to `--count` messages from `$DeadLetterQueue` in peek-lock mode (`max_wait_time=5`), preserves `message_id`, `correlation_id`, `content_type`, and `application_properties` (including W3C `traceparent` and native value types), increments `x-opt-replay-attempt`, records `x-original-deadletter-reason`, sends the message to the active queue, and completes the DLQ message. When `--remediate` is passed, remediation fails closed if JSON parsing fails or `simulate_poison` is not active:

```powershell
# Replay without modifying payload (for transient downstream recovery)
python scripts/day8/dlq_manager.py replay --count 5

# Replay and patch {"simulate_poison": true} -> {"simulate_poison": false, "remediated": true}
python scripts/day8/dlq_manager.py replay --count 5 --remediate
```

---

## 3. Operational Risks & Guardrails

1. **Unbounded Replay Loop Risk:** Replaying an un-remediated poison message without fixing the consumer or payload will cause it to fail 5 times again and return to `$DeadLetterQueue` with an incremented `x-opt-replay-attempt` header. Always inspect with `peek` before running `replay`.
2. **At-Least-Once Replay Window:** `replay_dlq()` calls `sender.send_messages(replayed_msg)` before `receiver.complete_message(msg)`. If the process crashes or loses network connectivity between those two calls, the message will be delivered to the active queue while remaining in the DLQ.
3. **In-Memory Idempotency Scope:** The consumer in `day2-function/function_app.py` deduplicates via an in-memory set (`PROCESSED_MESSAGE_IDS`) per Function worker instance. Duplicate deliveries from a partial replay failure are only suppressed if processed by the same warm worker instance.
