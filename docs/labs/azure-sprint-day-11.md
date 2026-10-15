# Azure sprint — Day 11: Local policy gate and structured audit evaluation

**Date:** 14 October 2026 (Asia/Kolkata)
**Status:** Implemented and validated locally through deterministic unit tests; no Azure resources, live queue operations, or Gemini API calls are used.

## 1. Objective and scope

Day 10 made the Day 9 `Decision` object transportable across Azure Service Bus inside a versioned `ArchitectureDecision.Created` envelope (`schemaVersion: 1`, `advisory: true`). Day 11 implements the downstream **local policy-gate and audit contract** (`scripts/day11/policy_gate.py`) that validates the incoming event envelope, enforces provenance-based policy boundaries, handles session-scoped duplicate event IDs deterministically, and emits a sanitized `AuditRecord`.

No new Azure resource is created, no live Service Bus call is made, no Gemini call is made, and `day2-function/function_app.py` remains untouched.

## 2. Architecture and evaluation flow

```text
Day 10 Event Envelope (ArchitectureDecision.Created, schemaVersion=1)
       |
       v
scripts/day11/policy_gate.py :: evaluate_decision_event(event, seen_event_ids)
       |
       +-- 1. Structural & Contract Validation
       |      - Mapping check; eventId must match [A-Za-z0-9._:-]{1,128}
       |      - eventType == "ArchitectureDecision.Created"
       |      - Invalid eventId is rejected and represented as "<invalid>" in the result
       |      - schemaVersion must be the integer 1 (reject bool, float 1.0, and string "1")
       |      - advisory is True
       |      - decision mapping with valid source ("rule" | "llm" | "unmatched")
       |        and non-empty normalized topic
       |      --> Fails closed: outcome="rejected", authorizes_execution=False
       |
       +-- 2. Session Deduplication Check (if seen_event_ids provided)
       |      - If eventId already in seen_event_ids:
       |      --> outcome="duplicate", reason_code="DUPLICATE_EVENT_ID"
       |      - Otherwise records eventId after envelope validation succeeds
       |
       +-- 3. Provenance & Topic Policy Gate
              - source == "llm"       --> outcome="non_actionable" (LLM_PROVENANCE_NON_ACTIONABLE)
              - source == "unmatched" --> outcome="non_actionable" (UNMATCHED_TOPIC_NON_ACTIONABLE)
              - source == "rule" & topic not in catalog
                                      --> outcome="non_actionable" (UNAPPROVED_RULE_TOPIC)
              - source == "rule", topic is in the catalog, and recommendation exactly matches PRINCIPLES[topic]
                                      --> outcome="pass_advisory" (APPROVED_RULE_TOPIC_ADVISORY_ONLY)
                                          actionable=False, authorizes_execution=False
```

## 3. Policy contract and audit schema

### Typed Return Values
* `AuditRecord`:
  * `event_id` (`str`): Validated event identifier (or `<missing>` / `<invalid>` on malformed envelopes).
  * `outcome` (`"pass_advisory" | "non_actionable" | "duplicate" | "rejected"`).
  * `reason_code` (`ReasonCode`): Machine-readable policy reason.
  * `source` (`str`): Provenance (`"rule"`, `"llm"`, `"unmatched"`, or `"unknown"`).
  * `policy_version` (`str`): `"2026-10-14.v1"`.
* `PolicyEvaluation`:
  * Contains all `AuditRecord` fields plus `actionable: Literal[False]`, `authorizes_execution: Literal[False]`, a human-readable `notice` explicitly stating that the result **does not authorize execution**, and the nested `audit: AuditRecord`.

### Data-Handling & Threat Boundaries
1. **No Execution Authority:** Every return path sets `actionable=False` and `authorizes_execution=False`. Even when a deterministic `rule` decision on an approved topic (`microservices`, `api`, `messaging`) achieves `outcome="pass_advisory"`, the evaluation explicitly states that it does not authorize automated execution or policy mutation.
2. **Untrusted Text Isolation (Prompt-Injection & Data-Leakage Guard):** Free-text fields (`decision.recommendation` and `decision.rationale`) may originate from an external LLM or untrusted caller input. `evaluate_decision_event()` never copies, formats, or logs `recommendation` or `rationale` into `AuditRecord` or `PolicyEvaluation`.
3. **Fail-Closed Envelope Validation:** Invalid envelopes are rejected before touching `seen_event_ids`, preventing malformed payloads with spoofed `eventId` values from poisoning the session deduplication set.
4. **Event ID Validation and Audit Safety:** `eventId` must be a string of 1–128 ASCII
   letters, digits, periods, underscores, colons, or hyphens. Invalid values—including
   control characters, newlines, and oversized values—are rejected. The returned result
   uses `<invalid>` rather than echoing the malformed identifier (`INVALID_EVENT_ID`); an
   absent ID is reported as `<missing>` (`MISSING_EVENT_ID`). This is input validation,
   not authentication of the event producer.

## 4. Assumptions and limitations

* **In-Memory Deduplication Scope:** Passing a `seen_event_ids` set to `evaluate_decision_event()` provides deterministic duplicate detection within a single Python process or batch evaluation run. It is **not** a durable cross-instance idempotency store. Production multi-worker consumers require a durable backing store (such as Azure Cosmos DB, Azure Cache for Redis, or database unique constraints) keyed by `eventId`.
* **Static Rule Catalog and Recommendation Integrity:** Approved rule topics come from the Day 9 PRINCIPLES catalog (microservices, api, messaging). A rule-backed event for an unknown topic is non_actionable with UNAPPROVED_RULE_TOPIC. For an approved topic, the recommendation must exactly match PRINCIPLES[topic]; a missing, malformed, or mismatched recommendation is non_actionable with RULE_RECOMMENDATION_MISMATCH. Passing these checks remains advisory only and never authorizes execution.

## 5. Reproduction and validation

From the repository root in PowerShell:

```powershell
# 1. Lint Day 11 module and unit tests
.\.venv\Scripts\ruff.exe check scripts/day11 tests/test_policy_gate.py

# 2. Run Day 9, Day 10, and Day 11 unit tests
.\.venv\Scripts\python.exe -m pytest tests/test_decision_model.py tests/test_decision_publisher.py tests/test_policy_gate.py -v

# 3. Bytecode compile check
.\.venv\Scripts\python.exe -m compileall -q scripts/day11 tests/test_policy_gate.py

# 4. Run the local CLI demo (offline, rule-backed)
.\.venv\Scripts\python.exe -m scripts.day11.policy_gate messaging
```

### Latest Validation Evidence (15 October 2026)

- Full repository test suite: **67 passed in 2.57s**.
- Full-suite command used a temporary `PYTHONPATH` pointing to `day2-function` so `function_app` could be imported during root-level test collection. The environment variable was removed after the run.
- Day 11 targeted policy-gate suite: **26 passed in 0.95s**.
- Repository-wide Ruff: **five findings** in existing files outside the Day 11 policy-gate scope. Targeted Day 11 Ruff checks passed.
- Compilation: `python -m compileall -q scripts tests` completed without reported errors.
- `git diff --check`: no whitespace errors; Git emitted LF-to-CRLF line-ending warnings.
- No Azure resources were provisioned, and no live Service Bus or Gemini calls were made for this validation.
