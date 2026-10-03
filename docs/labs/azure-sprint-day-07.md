# Azure Sprint Day 7: Distributed Tracing & W3C Correlation Context

## 1. Objective
Implement end-to-end observability and distributed tracing across an asynchronous, decoupled Azure Integration Services pipeline (Logic Apps -> Service Bus -> Azure Functions) using the W3C Trace Context standard (`traceparent`).

## 2. Concepts Learned
- **W3C Trace Context Standard**: Formatting correlation data as `00-<trace-id>-<parent-id>-<trace-flags>`.
- **Asynchronous Context Propagation**: Preserving distributed trace trees across message brokers where synchronous thread contexts break.
- **Service Bus Application Properties**: Leveraging user properties (`traceparent`, `Diagnostic-Id`) and system broker properties (`correlation_id`).
- **Log Correlation in Azure Monitor**: Linking application traces, requests, and dependencies under a unified `operation_Id`.

## 3. Architectural Reasoning
In decoupled messaging architectures, HTTP request scopes terminate at the message broker. Without explicit trace context propagation, operations downstream appear as isolated, root-level executions, making failure triage across microservices nearly impossible. By adhering to the W3C standard, distributed spans stitch together seamlessly into Azure Monitor Application Map and end-to-end transaction views.

## 4. Decisions & Alternatives
- **W3C `traceparent` vs Custom Headers**: Adopted W3C standard over proprietary correlation headers to align with OpenTelemetry and Azure SDK defaults.
- **Regex Extraction with Fallback**: Implemented robust regex extraction with graceful fallback to `message.correlation_id` to prevent message loss on non-compliant payloads.

## 5. Security & RBAC Model
- **Producer Authentication**: Script uses `DefaultAzureCredential` via Entra ID with `Azure Service Bus Data Sender` role.
- **Namespace Security**: Local shared access key authentication remains disabled (`--disable-local-auth true`).

## 6. Validation & Runtime Evidence
- Dispatched test message with explicit W3C `traceparent` (`00-c652426416264057be7d52b610590581-4c5c73daf7b343f6-01`).
- Verified queue consumption: `ActiveMessages: 0`, `DeadLetterMessages: 0`.
- Unit test suite expanded from 9 to 12 tests, validating W3C extraction, correlation fallback, and empty property scenarios.

## 7. Cost Considerations
- Standard Service Bus namespace reused (`sb-ai-int-likwmn7js4ffw`). Zero incremental compute or resource cost incurred.
