from datetime import datetime, timezone
from importlib import import_module

import pytest

decision_model = import_module("01_tool_calling.first_agent")
publisher = import_module("scripts.day10.publish_decision")
policy_gate = import_module("scripts.day11.policy_gate")


def _sample_event(
    *,
    topic: str = "messaging",
    source: str = "rule",
    recommendation: str = (
    "Assume messages can be duplicated and design consumers to be idempotent."
),
    rationale: str = "SECRET-RATIONALE-SENTINEL",
    event_id: str = "evt-100",
) -> dict:
    decision = decision_model.Decision(
        topic=topic,
        recommendation=recommendation,
        source=source,  # type: ignore[arg-type]
        rationale=rationale,
    )
    return publisher.build_decision_event(
        decision,
        event_id=event_id,
        occurred_at=datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc),
    )


def test_rule_backed_catalog_topic_passes_advisory_gate_without_authorizing_execution():
    event = _sample_event(topic="messaging", source="rule", event_id="evt-rule-001")

    result = policy_gate.evaluate_decision_event(event)

    assert result.outcome == "pass_advisory"
    assert result.reason_code == "APPROVED_RULE_TOPIC_ADVISORY_ONLY"
    assert result.source == "rule"
    assert result.actionable is False
    assert result.authorizes_execution is False
    assert "does not authorize execution" in result.notice
    assert result.audit == policy_gate.AuditRecord(
        event_id="evt-rule-001",
        outcome="pass_advisory",
        reason_code="APPROVED_RULE_TOPIC_ADVISORY_ONLY",
        source="rule",
        policy_version=policy_gate.POLICY_VERSION,
    )
    audit_repr = repr(result.audit)
    assert "SECRET-RECOMMENDATION-SENTINEL" not in audit_repr
    assert "SECRET-RATIONALE-SENTINEL" not in audit_repr


def test_rule_source_with_unapproved_topic_is_non_actionable():
    event = _sample_event(topic="quantum-mesh", source="rule", event_id="evt-rule-002")

    result = policy_gate.evaluate_decision_event(event)

    assert result.outcome == "non_actionable"
    assert result.reason_code == "UNAPPROVED_RULE_TOPIC"
    assert result.source == "rule"
    assert result.actionable is False
    assert result.authorizes_execution is False
    assert "does not authorize execution" in result.notice

def test_hostile_event_id_is_rejected_without_leaking_raw_value():
    hostile_id = "evt-hostile\nINJECTED-\x1b[31m" + ("X" * 129)
    event = _sample_event(topic="messaging", event_id=hostile_id)

    result = policy_gate.evaluate_decision_event(event)

    assert result.outcome == "rejected"
    assert result.reason_code == "INVALID_EVENT_ID"
    assert result.event_id == "<invalid>"
    assert hostile_id not in repr(result)
    assert "INJECTED" not in repr(result)
    assert result.actionable is False
    assert result.authorizes_execution is False

@pytest.mark.parametrize(
    "recommendation",
    [
        "Forged recommendation",
        None,
        123,
    ],
)

def test_rule_recommendation_must_match_catalog_exactly(recommendation):
    event = _sample_event(
        topic="messaging",
        source="rule",
        recommendation=recommendation,  # type: ignore[arg-type]
        rationale="SECRET-RATIONALE-SENTINEL",
        event_id="evt-forged-recommendation",
    )

    result = policy_gate.evaluate_decision_event(event)

    assert result.outcome == "non_actionable"
    assert result.reason_code == "RULE_RECOMMENDATION_MISMATCH"
    assert result.actionable is False
    assert result.authorizes_execution is False
    assert "SECRET-RATIONALE-SENTINEL" not in repr(result)
    assert "Forged recommendation" not in repr(result)


def test_llm_decision_is_always_non_actionable_and_omits_body_text():
    event = _sample_event(
        topic="messaging",
        source="llm",
        recommendation="UNTRUSTED-LLM-PROMPT-OUTPUT",
        rationale="UNTRUSTED-LLM-RATIONALE",
        event_id="evt-llm-001",
    )

    result = policy_gate.evaluate_decision_event(event)

    assert result.outcome == "non_actionable"
    assert result.reason_code == "LLM_PROVENANCE_NON_ACTIONABLE"
    assert result.source == "llm"
    assert result.actionable is False
    assert result.authorizes_execution is False
    assert "does not authorize execution" in result.notice
    assert "UNTRUSTED-LLM-PROMPT-OUTPUT" not in repr(result)
    assert "UNTRUSTED-LLM-RATIONALE" not in repr(result)


def test_unmatched_decision_is_non_actionable():
    event = _sample_event(topic="event sourcing", source="unmatched", event_id="evt-unmatched-001")

    result = policy_gate.evaluate_decision_event(event)

    assert result.outcome == "non_actionable"
    assert result.reason_code == "UNMATCHED_TOPIC_NON_ACTIONABLE"
    assert result.source == "unmatched"
    assert result.actionable is False
    assert result.authorizes_execution is False


def test_duplicate_event_id_is_detected_deterministically_in_session():
    seen: set[str] = set()
    event = _sample_event(
        topic="api",
        source="rule",
        recommendation="Design APIs around stable contracts and explicit ownership.",
        event_id="evt-dup-001",
    )

    first = policy_gate.evaluate_decision_event(event, seen_event_ids=seen)
    second = policy_gate.evaluate_decision_event(event, seen_event_ids=seen)

    assert first.outcome == "pass_advisory"
    assert first.reason_code == "APPROVED_RULE_TOPIC_ADVISORY_ONLY"
    assert second.outcome == "duplicate"
    assert second.reason_code == "DUPLICATE_EVENT_ID"
    assert second.event_id == "evt-dup-001"
    assert second.source == "rule"
    assert second.actionable is False
    assert second.authorizes_execution is False


@pytest.mark.parametrize(
    ("mutator", "expected_reason", "expected_event_id"),
    [
        (lambda e: e.update({"eventId": "   "}), "INVALID_EVENT_ID", "<invalid>"),
        (lambda e: e.pop("eventId"), "MISSING_EVENT_ID", "<missing>"),
        (lambda e: e.update({"eventId": None}), "MISSING_EVENT_ID", "<missing>"),
        (lambda e: e.update({"eventId": 123}), "INVALID_EVENT_ID", "<invalid>"),
        (lambda e: e.update({"eventId": "bad\nINJECTED"}), "INVALID_EVENT_ID", "<invalid>"),
        (lambda e: e.update({"eventId": "x" * 129}), "INVALID_EVENT_ID", "<invalid>"),
        (lambda e: e.update({"eventType": "Other.Event"}), "UNSUPPORTED_EVENT_TYPE", "evt-100"),
        (lambda e: e.update({"schemaVersion": 2}), "UNSUPPORTED_SCHEMA_VERSION", "evt-100"),
        (lambda e: e.update({"schemaVersion": True}), "UNSUPPORTED_SCHEMA_VERSION", "evt-100"),
        (lambda e: e.update({"schemaVersion": 1.0}), "UNSUPPORTED_SCHEMA_VERSION", "evt-100"),
        (lambda e: e.update({"schemaVersion": "1"}), "UNSUPPORTED_SCHEMA_VERSION", "evt-100"),
        (lambda e: e.update({"advisory": False}), "NON_ADVISORY_REJECTED", "evt-100"),
        (lambda e: e.update({"advisory": "true"}), "NON_ADVISORY_REJECTED", "evt-100"),
        (lambda e: e.update({"decision": "not-a-dict"}), "INVALID_DECISION_PAYLOAD", "evt-100"),
        (
            lambda e: e["decision"].update({"source": "external"}),
            "INVALID_DECISION_SOURCE",
            "evt-100",
        ),
        (
            lambda e: e["decision"].update({"topic": "   "}),
            "INVALID_DECISION_PAYLOAD",
            "evt-100",
        ),
    ],
)
def test_invalid_envelopes_are_rejected_and_do_not_pollute_dedupe_set(
    mutator, expected_reason: str, expected_event_id: str
):
    seen: set[str] = set()
    event = _sample_event(event_id="evt-100")
    mutator(event)

    result = policy_gate.evaluate_decision_event(event, seen_event_ids=seen)

    assert result.outcome == "rejected"
    assert result.reason_code == expected_reason
    assert result.event_id == expected_event_id
    assert result.actionable is False
    assert result.authorizes_execution is False
    assert seen == set()


def test_non_mapping_envelope_is_rejected():
    result = policy_gate.evaluate_decision_event(["not", "a", "mapping"])  # type: ignore[arg-type]

    assert result.outcome == "rejected"
    assert result.reason_code == "INVALID_ENVELOPE"
    assert result.event_id == "<invalid>"
    assert result.authorizes_execution is False
