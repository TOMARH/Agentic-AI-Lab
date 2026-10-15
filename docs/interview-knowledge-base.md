## Day 7: Distributed Tracing, W3C Context & Telemetry Correlation

### Core Concepts & Architecture Mechanics
- **W3C Trace Context Standard (`traceparent`)**:
  - Format: `00-<32 hex trace_id>-<16 hex parent_id>-<2 hex trace_flags>`.
  - Enables vendor-neutral distributed tracing across independent microservices and message brokers.
- **Asynchronous Context Boundary Problem**:
  - In synchronous HTTP chains, thread context or request headers propagate naturally.
  - In asynchronous messaging (Service Bus, Event Grid), queues break the synchronous HTTP context. Producers must explicitly inject trace context into message application properties (`traceparent`, `Diagnostic-Id`) or system properties (`correlation_id`).
- **Consumer Telemetry Correlation**:
  - Consumers parse the incoming `traceparent` using regex or OpenTelemetry extractors.
  - Log entries and spans link to the incoming `trace_id` as `operation_Id` and `parent_id` as `operation_ParentId`, maintaining the unified trace tree in Azure Monitor / Log Analytics.

### Enterprise Interview Talking Points
- **Q: How do you track an end-to-end transaction through Azure Service Bus into a consumer Function?**
  - *Answer:* "Because Service Bus decouples execution asynchronously, we pass the W3C `traceparent` header in the message's `application_properties` (and mirror it to `Diagnostic-Id`). In the consumer Function, we extract the 32-character trace ID and 16-character parent span ID, injecting them into our structured logging dimensions. In Application Insights and Log Analytics, the entire lifecycle across producer, queue, and consumer correlates under a single `operation_Id`."
- **Q: Why use W3C `traceparent` instead of a custom correlation GUID?**
  - *Answer:* "The W3C Trace Context specification is the industry standard natively supported by OpenTelemetry, Application Insights, and Azure SDKs. Adhering to W3C avoids vendor lock-in, eliminates manual header-mapping code across multi-cloud/hybrid services, and allows Azure Monitor Application Map to stitch dependency trees automatically."

---

## Days 9–11: Provenance-Aware Agent Decisions, Event Contracts & Policy Gates

### Core Concepts & Architecture Mechanics
- **Rules-First Decision Provenance (Day 9)**:
  - Deterministic local rules (`source="rule"`) are evaluated before any optional model fallback (`source="llm"`), and unknown topics without a model fallback return an explicit `source="unmatched"` state.
- **Advisory Event Envelope Across Service Bus (Day 10)**:
  - Decisions are serialized into a versioned `ArchitectureDecision.Created` (`schemaVersion: 1`) envelope with `advisory: true` enforced across all sources, capped at 240 KiB before Entra ID (`DefaultAzureCredential`) authentication.
  - Transport correlation headers (`traceparent`, `Diagnostic-Id`, `correlation_id`) are carried in Service Bus message properties and validated against malformed or all-zero identifiers without claiming an exported OpenTelemetry producer span when no tracer is active.
- **Fail-Closed Policy Gate & Redacted Audit Records (Day 11)**:
  - Downstream evaluation (`scripts/day11/policy_gate.py`) validates the envelope contract before consulting session deduplication: `eventType` must match `ArchitectureDecision.Created`; `schemaVersion` must be the integer `1` (booleans, floats such as `1.0`, and strings such as `"1"` are rejected); `advisory` must be `True`; and `decision.source` must be valid.
  - `eventId` must match `[A-Za-z0-9._:-]{1,128}`: 1–128 ASCII letters, digits, periods, underscores, colons, or hyphens. Invalid IDs are rejected with `INVALID_EVENT_ID` and represented as `<invalid>` so the malformed value is not echoed; absent IDs use `MISSING_EVENT_ID` and `<missing>`. This validates input shape; it does not authenticate the event producer.
  - LLM and unmatched decisions are strictly `non_actionable`. Cataloged rule-backed decisions may pass the advisory gate (`pass_advisory`), but every outcome sets `actionable=False` and `authorizes_execution=False`.
  - Structured `AuditRecord` outputs capture only `event_id`, `outcome`, `reason_code`, `source`, and `policy_version`—omitting `recommendation` and `rationale` text to prevent untrusted model output or sensitive text from leaking into audit logs.

### Enterprise Interview Talking Points
- **Q: How do you prevent LLM recommendations in an event-driven architecture from being treated as executable commands by downstream consumers?**
  - *Answer:* "We enforce defense in depth at three layers: first, the producer tags every decision with explicit provenance (`rule`, `llm`, or `unmatched`) and sets `advisory: true` in the versioned event schema; second, the downstream policy gate fails closed if `advisory` is not `True` and classifies all `llm` and `unmatched` sources as `non_actionable`; third, even when a deterministic `rule` topic passes the policy check (`pass_advisory`), the evaluation contract explicitly sets `authorizes_execution=False` and strips free-text `recommendation` and `rationale` fields from the structured audit record."
- **Q: Why separate in-memory session deduplication from durable idempotency in your policy gate documentation?**
  - *Answer:* "In-memory deduplication (`seen_event_ids`) deterministically suppresses duplicate `eventId` deliveries within a single process or batch run, and we only record an `eventId` after structural validation passes so malformed payloads cannot poison the set. However, in a distributed serverless consumer with scale-out and restarts, true idempotency requires a durable state store or transactional outbox keyed by `eventId`."
