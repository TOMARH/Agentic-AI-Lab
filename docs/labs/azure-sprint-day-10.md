# Azure sprint — Day 10: Publish typed decisions through existing Service Bus

**Date:** 14 October 2026 (Asia/Kolkata)
**Status:** Implemented and validated locally; one rule-backed live message was sent to the existing queue on 14 October 2026.

## 1. Objective and concepts

Carry the Day 9 local `Decision` value across an asynchronous boundary by publishing it to the existing Azure Service Bus queue. The lab demonstrates a versioned integration event, preservation of provenance, Entra ID authentication, W3C trace context, and compatibility with an existing generic JSON consumer.

No new namespace, queue, Function, identity, role assignment, or other Azure resource is required. No Function source change is part of this lab.

## 2. Readiness and reasoning checkpoint

The user selected the track “carry Day 9 decisions into the existing Service Bus flow.” Read-only checks on 14 October 2026 confirmed:

- Subscription `e5939949-6509-48de-964b-5f1b65c34714` is enabled in tenant `70a887c3-533b-4cdb-89a3-4ed571acb2a0`.
- Resource group `rg-ai-azure-integration-lab` already contains Service Bus namespace `sb-ai-int-likwmn7js4ffw`, the existing Function App, and the DLQ metric alert.
- The queue `integration-events` is active. At inspection it had 0 active, 0 dead-letter, and 0 scheduled messages.
- Queue-scoped RBAC already includes the user's Azure Service Bus Data Sender and Data Receiver roles. No role assignment change is needed.
- The namespace was provisioned as Standard in Central India in the Day 4 record. Its Standard-tier recurring charge continues. A current subscription spend figure was not available from the connected Azure tools; no fixed cost estimate is claimed.

The Day 9 PR is the source for this dependent lab and remains separately governed by its own review/merge gate. The new work is on a Day 10 branch based on that Day 9 implementation; do not merge it directly into protected `main`.

## 3. Architecture and event contract

```text
Day 9 decide(topic)
       |
       v
Decision(topic, recommendation, source, rationale)
       |
       v
scripts/day10/publish_decision.py
  DefaultAzureCredential + queue-scoped Data Sender
       |
       v
existing Service Bus / integration-events
       |
       v
existing Day 4 Function consumer
  parse valid JSON; log message metadata only; complete on success
```

The event body is JSON with `eventType`, `schemaVersion`, `eventId`, `occurredAt`, and a nested `decision` object containing all four Day 9 fields. The Service Bus `message_id` equals `eventId`. W3C `traceparent` and `Diagnostic-Id` are transport properties; business decision fields are not duplicated into properties.

An `unmatched` result is an explicit event outcome, not a request to execute a recommendation. A source of `llm` remains advisory and untrusted. Only the explicit `--llm` option can call Gemini, and that call is separate from the Service Bus operation.

## 4. Design decisions and ADR

See [ADR 0007](../adr/0007-decision-events-to-existing-servicebus.md) for alternatives and consequences. In brief:

1. Reuse the existing queue and generic JSON consumer contract instead of adding a new namespace or queue.
2. Keep the Function consumer unchanged; this lab carries the decision but does not make it a policy or authorization input.
3. Put business data in a versioned event body and reserve application properties for trace context.
4. Use existing Entra ID and queue-level Data Sender access; do not create a SAS key, connection string, or new role assignment.

## 5. Tools and configuration

The root `requirements.txt` pins `azure-identity` and `azure-servicebus`. The local environment observed before implementation had Azure Identity 1.25.3 and Service Bus SDK 7.14.3; the updated project pins use the upstream stable SDK releases 1.26.0 and 7.15.0. The Day 2 Function keeps its independent requirements file unchanged. See [Tools & Technology](../tools/README.md).

Configuration is process-scoped and optional; defaults target the existing lab queue:

| Variable | Default | Purpose |
|---|---|---|
| `SERVICE_BUS_FQDN` | `sb-ai-int-likwmn7js4ffw.servicebus.windows.net` | Target namespace hostname |
| `SERVICE_BUS_QUEUE_NAME` | `integration-events` | Target queue |
| `GEMINI_API_KEY` | unset | Needed only for `--llm` on a topic without a local rule |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Optional model override for the explicitly enabled fallback |

`DefaultAzureCredential` uses the developer's configured Entra credential chain. The signed-in identity needs Azure Service Bus Data Sender at the queue scope. The lab does not print credential material, message body, recommendation, or rationale to the console.

## 6. Reproduction and validation

From the repository root in PowerShell:

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
ruff check scripts/day10 tests/test_decision_publisher.py
python -m pytest tests/test_decision_model.py tests/test_decision_publisher.py -v
python -m scripts.day10.publish_decision messaging
```

The first three commands are local validation. Unit tests use fake credentials, sender/client objects, and deterministic timestamps/trace IDs. They do not call Azure or Gemini. The final command sends one rule-backed event to the live queue and may incur a Service Bus operation charge. Do not add `--llm` to a live command unless a Gemini request is intended and approved by account/data policy.

Validation evidence from 14 October 2026:

- Ruff: `All checks passed!` for `scripts/day10` and `tests/test_decision_publisher.py`.
- Pytest: 10 passed across the Day 9 decision model and Day 10 publisher tests.
- Compile check: `python -m compileall -q scripts/day10 tests/test_decision_publisher.py` completed successfully. The local Python launcher emitted a warning that it could not locate its registered Python executable, but the selected interpreter ran the command successfully.
- `git diff --check`: passed.
- Live rule-only send: event `18caa9295cf34ad99b7830039c5eb4d0` was published to `integration-events` using source `rule`; no Gemini call was made.
- Queue counts immediately before the send were 0 active, 0 dead-letter, and 0 scheduled. Afterward all queue message counts were 0, consistent with the existing consumer having completed the message.
- Correlated Function telemetry could not be queried: there is no Log Analytics workspace in the resource group, and the App Insights component query endpoint did not expose the `AppTraces` table. Therefore consumer completion is inferred from the queue counts, not directly confirmed in traces.

Never copy the decision body or credentials into a log or PR comment.

## 7. Security and reliability

- Entra ID authentication and the existing queue-scoped Data Sender role avoid SAS secrets and broader namespace-level access.
- A live model fallback can send the topic to Google; keep it disabled for the Azure smoke test.
- The consumer does not log message bodies. The event body still contains a recommendation and rationale, so avoid confidential or regulated input.
- The queue uses at-least-once delivery. `eventId`/`message_id` can support future durable deduplication, but the existing in-memory consumer idempotency is not a durable business ledger.
- The generated event does not set `simulate_poison`; malformed content or transport failures retain the existing queue retry/dead-letter semantics.
- The SDK manages transient send retries. The CLI sends one message and exits; it has no unattended retry loop.

## 8. Cost, cleanup, and resource state

The namespace is already Standard and continues its existing recurring charge. This lab creates no Azure resources; one live send uses normal Service Bus operation capacity. Current subscription spend could not be verified through the available Azure tools, so no amount is stated. No cloud cleanup is required. The queue returned to zero active and dead-letter messages after the smoke-test send; direct consumer telemetry was unavailable as noted above.

## 9. Next-lab dependency and interview takeaways

Day 10 makes the Day 9 decision contract transportable. A later lab can add a consumer that validates a decision against explicit policy and records an auditable outcome; until then, the message is informational and must not authorize or execute work.

- Put a versioned contract on the message body and transport concerns in headers/properties.
- Carry provenance so downstream systems can distinguish deterministic rules, model suggestions, and unmatched topics.
- Reuse existing queue infrastructure and scoped identity grants to reduce cost and avoid duplicate architecture.
- Treat queue delivery as at-least-once and model text as untrusted, even when the event is strongly typed in the producer.
