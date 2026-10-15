# Azure sprint — Day 15: Offline serialized decision boundary

## Objective

Connect the serialized Day 10 `ArchitectureDecision.Created` event to the Day 11 policy gate locally. The boundary parses JSON, delegates envelope validation and policy evaluation, and returns only the sanitized audit outcome.

## Contract coverage

`scripts/day15/offline_boundary.py` accepts a serialized JSON string, passes the parsed envelope to `evaluate_decision_event`, and returns the audit record as a plain dictionary. Focused tests use events built by the Day 10 publisher and cover:

- A valid publisher-produced rule event that passes as advisory only.
- A non-advisory event rejected by policy.
- A repeated event ID reported as a duplicate within the caller-provided in-memory set.
- Invalid JSON raising `json.JSONDecodeError` so a transport adapter does not acknowledge it and can retain its retry and eventual dead-letter behavior.

Only the policy gate's `AuditRecord` is returned. Recommendation and rationale text are excluded. Every policy outcome remains non-actionable and does not authorize execution.

## Scope and limitations

This is an offline Python boundary. It does not publish or receive Service Bus messages, authenticate, contact Azure, or change Azure resources. The live Day 2 Function consumer remains unchanged. Duplicate tracking is session-scoped in-memory state; this does not establish durable idempotency or broker delivery behavior.
