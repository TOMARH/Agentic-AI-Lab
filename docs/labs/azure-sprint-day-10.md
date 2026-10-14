# Azure sprint — Day 10: Publish typed decisions through existing Service Bus

**Date:** 14 October 2026 (Asia/Kolkata)
**Status:** Implemented and validated locally; one rule-backed live message was sent to the existing queue on 14 October 2026.

## 1. Objective and concepts

Carry the Day 9 local `Decision` value across an asynchronous boundary by publishing it to the existing Azure Service Bus queue. The lab demonstrates a versioned integration event, preservation of provenance, Entra ID authentication, W3C-formatted correlation headers (`traceparent` and `Diagnostic-Id`), and compatibility with an existing generic JSON consumer.

No new namespace, queue, Function, identity, role assignment, or other Azure resource is required. No Function source change is part of this lab.

## 2. Readiness and reasoning checkpoint

The user selected the track “carry Day 9 decisions into the existing Service Bus flow.” Read-only checks on 14 October 2026 confirmed:

- The signed-in Azure subscription is enabled and has the `rg-ai-azure-integration-lab` resource group.
- That resource group already contains the Service Bus namespace, the existing Function App, and the DLQ metric alert.
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

The event body is JSON with `eventType`, `schemaVersion`, `advisory`, `eventId`, `occurredAt`, and a nested `decision` object containing all four Day 9 fields. `advisory` is always `true`, regardless of source; downstream consumers must not execute or authorize work from this event. `decision.source` separately identifies rule, LLM, or unmatched provenance. The Service Bus `message_id` equals `eventId`. W3C-formatted `traceparent` and `Diagnostic-Id` headers carry correlation-only context (the CLI does not initialize an OpenTelemetry tracer or export a producer span); business decision fields are not duplicated into properties.

An `unmatched` result is an explicit event outcome, not a request to execute a recommendation. A source of `llm` remains advisory and untrusted. Only the explicit `--llm` option can call Gemini, and that call is separate from the Service Bus operation.

## 4. Design decisions and ADR

See [ADR 0007](../adr/0007-decision-events-to-existing-servicebus.md) for alternatives and consequences. In brief:

1. Reuse the existing queue and generic JSON consumer contract instead of adding a new namespace or queue.
2. Keep the Function consumer unchanged; this lab carries the decision but does not make it a policy or authorization input.
3. Put business data in a versioned event body and reserve application properties for W3C-formatted correlation headers (rejecting malformed or all-zero IDs).
4. Use existing Entra ID and queue-level Data Sender access; do not create a SAS key, connection string, or new role assignment.

## 5. Tools and configuration

The root `requirements.txt` pins `azure-identity` and `azure-servicebus`. The local environment observed before implementation had Azure Identity 1.25.3 and Service Bus SDK 7.14.3; the updated project pins use the upstream stable SDK releases 1.26.0 and 7.15.0. The Day 2 Function keeps its independent requirements file unchanged. See [Tools & Technology](../tools/README.md).

The namespace hostname is a required process setting, so a clone of this public repository does not silently target the author's lab resource. The queue name defaults to the existing lab queue:

| Variable | Default | Purpose |
|---|---|---|
| `SERVICE_BUS_FQDN` | required | Target namespace hostname |
| `SERVICE_BUS_QUEUE_NAME` | `integration-events` | Target queue |
| `GEMINI_API_KEY` | unset | Needed only for `--llm` on a topic without a local rule |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Optional model override for the explicitly enabled fallback |

`DefaultAzureCredential` uses its configured Entra credential chain. For this operator-run CLI, run `az login`, select the intended subscription with `az account set --subscription "<subscription ID or name>"`, and verify it using `az account show --query "{subscription:id, tenant:tenantId, user:user.name}" -o table` before publishing. If the environment has other credential sources configured, verify which identity `DefaultAzureCredential` selects. The identity needs Azure Service Bus Data Sender at the queue scope. The lab does not print credential material, message body, recommendation, or rationale to the console.

## 6. Reproduction and validation

From the repository root in PowerShell:

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
ruff check scripts/day10 tests/test_decision_publisher.py
python -m pytest tests/test_decision_model.py tests/test_decision_publisher.py -v
$env:SERVICE_BUS_FQDN = "<your namespace>.servicebus.windows.net"
python -m scripts.day10.publish_decision messaging
```

The first three commands are local validation. Unit tests use fake credentials, sender/client objects, and deterministic timestamps/correlation IDs. They do not call Azure or Gemini. The final command sends one rule-backed event to the live queue; Standard includes the first 13 million messaging operations each month, and operations beyond the allowance are billed. Do not add `--llm` to a live command unless a Gemini request is intended and approved by account/data policy.

Validation evidence from 14 October 2026:

- Ruff: `All checks passed!` for `scripts/day10` and `tests/test_decision_publisher.py`.
- Pytest: 21 passed across the Day 9 decision model (5 tests) and Day 10 publisher tests (16 tests), covering the advisory marker, namespace requirement, event-size guard, W3C correlation header validation (including non-zero trace/span ID enforcement), client/sender/credential cleanup on failure paths, and CLI failure behavior.
- The tests were run after installing the exact pins: `azure-identity` 1.26.0, `azure-servicebus` 7.15.0, `pytest` 9.1.1, `ruff` 0.16.10, and `google-genai` 2.23.0.
- CI's Ruff scope is the new Day 10 publisher and its tests; the Day 9 model and tests are exercised by pytest but are not re-linted in this PR.
- Compile check: `python -m compileall -q scripts/day10 tests/test_decision_publisher.py` completed successfully.
- `git diff --check`: passed.
- Live rule-only send: event `18caa9295cf34ad99b7830039c5eb4d0` was published to `integration-events` using source `rule`; no Gemini call was made. This historical smoke send used the then-installed `azure-identity` 1.25.3 and `azure-servicebus` 7.14.3.
- At 2026-10-14 13:56:27.624786 UTC, Application Insights returned `Consuming message: ID=18caa9295cf34ad99b7830039c5eb4d0` with `TraceSource=traceparent` and component `operation_Id` `461227dd2e394b9ab64c04525148c7d2`. This correlates the consumer log by message ID and confirms the consumer parsed the W3C-formatted `traceparent` property (`TraceSource=traceparent`). Because the CLI generates synthetic W3C correlation IDs without exporting a producer telemetry span and the Function log's structured `TraceId` dimension was empty, end-to-end distributed trace export from producer to Application Insights is not claimed. This historical event predates the explicit `advisory` property added to the PR after review.
- To query this evidence through the Application Insights component API, select the intended subscription and run the following KQL against its `traces` table (the component API schema differs from Log Analytics' `AppTraces`):

  ```powershell
  az monitor app-insights query --app day2fnsprint29 --resource-group rg-ai-azure-integration-lab --analytics-query "traces | where message contains 'Consuming message: ID=18caa9295cf34ad99b7830039c5eb4d0' | project timestamp, message, operation_Id | take 5"
  ```
- Immediately before send, the queue had 0 active, 0 dead-letter, and 0 scheduled messages. At 2026-10-14 14:36:59 UTC, it had 0 active, 0 dead-letter, 0 scheduled, and 0 total messages. Queue duplicate detection is disabled (`requiresDuplicateDetection=false`; the reported `PT10M` history window is inactive); an ambiguous send retry can create duplicates, so consumers must remain idempotent.
- The CI job runs for PRs targeting both `main` and the current stacked Day 9 base branch, so this PR can receive a GitHub Actions result before Day 9 merges.

Never copy the decision body or credentials into a log or PR comment.

## 7. Security and reliability

- Entra ID authentication and the existing queue-scoped Data Sender role avoid SAS secrets and broader namespace-level access.
- A live model fallback can send the topic to Google; keep it disabled for the Azure smoke test.
- The consumer does not log message bodies. The event body still contains a recommendation and rationale, so avoid confidential or regulated input.
- The queue uses at-least-once delivery. `eventId`/`message_id` can support future durable deduplication, but the existing in-memory consumer idempotency is not a durable business ledger.
- The generated event does not set `simulate_poison`; malformed content or transport failures retain the existing queue retry/dead-letter semantics.
- The SDK manages transient send retries. The CLI sends one message and exits; it has no unattended retry loop. Because duplicate detection is disabled, a retry after a timeout with uncertain service acceptance can result in duplicate delivery.
- Service Bus Standard messages are limited to 256 KB. This producer caps the UTF-8 JSON body at 240 KiB to leave room for transport overhead; a larger event is rejected before authentication or network access. The decision fields remain untrusted input and are not truncated or sanitized.
- Every event includes machine-readable `advisory: true`; future consumers must validate this flag and still apply their own policy and approval checks.

## 8. Cost, cleanup, and resource state

The existing Standard namespace's base charge continues. Standard includes the first 13 million messaging operations each month; the smoke test used one send operation, though total subscription usage against that allowance was not available to verify. See [Microsoft Service Bus pricing](https://azure.microsoft.com/en-in/pricing/details/service-bus/). Current subscription spend could not be verified through the available Azure tools, so no total is stated. This lab creates no resources to delete. Keep the namespace in the sprint's final teardown/cost review; it continues billing until the shared lab resource is removed or otherwise changed. The queue returned to zero active and dead-letter messages after the smoke-test send, and a correlated Function trace is recorded above.

## 9. Next-lab dependency and interview takeaways

Day 10 makes the Day 9 decision contract transportable. A later lab can add a consumer that validates a decision against explicit policy and records an auditable outcome; until then, the message is informational and must not authorize or execute work.

- Put a versioned contract on the message body and transport concerns in headers/properties.
- Carry provenance so downstream systems can distinguish deterministic rules, model suggestions, and unmatched topics.
- Reuse existing queue infrastructure and scoped identity grants to reduce cost and avoid duplicate architecture.
- Treat queue delivery as at-least-once and model text as untrusted, even when the event is strongly typed in the producer.
