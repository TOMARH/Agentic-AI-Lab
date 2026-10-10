# Azure sprint — Day 8: Dead-letter queue inspection and replay tooling

## Objectives & Architecture

Day 8 establishes an attended operator CLI workflow for safely inspecting, analyzing, and replaying poisoned messages trapped in Azure Service Bus Dead-Letter Queues (DLQ).

                      [Service Bus Queue: integration-events]
                                          │
                                          ▼ (delivery failure x5 / MaxDeliveryCountExceeded)
                                  [$DeadLetterQueue]
                                          │
                ┌─────────────────────────┴─────────────────────────┐
                ▼                                                   ▼
        [dlq_manager.py peek]                              [dlq_manager.py replay]
 (Non-destructive peek_messages)                    (peek_lock mode: receive_messages)
  • Inspects headers & payload                       • Receives message with active lock
  • Audits DeadLetterReason / ErrorDescription       • If --remediate: sanitizes JSON body
  • No lock acquired, sequence unchanged             • Step 1: send_messages() to primary queue
                                                     • Step 2: complete_message() on DLQ
                                                                    │
                                                                    ▼
                                               [Risk: Network failure between Step 1 & 2]
                                               • Original message remains in DLQ (duplicate)
                                               • Safe ONLY because Consumer deduplicates on message_id

### Core Design Decisions
1. **Attended CLI Operations:** DLQ inspection and drainage are implemented as an operator-facing CLI utility (`scripts/day8/dlq_manager.py`) to validate triage and remediation hypotheses before introducing unattended automated alert remediation (Day 9).
2. **Trace Context Continuity:** Replayed messages retain inbound W3C `traceparent` diagnostic headers and `correlation_id` values, ensuring distributed telemetry in Application Insights links the remediation back to the root-cause failure.
3. **Payload Sanitization (`--remediate`):** When `--remediate` is enabled, the toxic flag (`simulate_failure: true`) inside the JSON message body is rewritten to `false` before re-enqueuing.
4. **At-Least-Once Delivery Ordering:** Replay dispatches `send_messages()` to the primary queue *before* executing `complete_message()` on the DLQ. This guarantees messages are never lost if an unexpected termination occurs mid-flight, accepting duplicate delivery over permanent data loss.

---

## Prerequisites & Configuration

### 1. Local Environment & Dependencies
All scripts require the project virtual environment with Azure messaging libraries installed:

```powershell
# Activate local virtual environment
.venv\Scripts\Activate.ps1

# Verify core dependencies
pip install azure-servicebus azure-identity pytest ruff