"""Day 15 boundary and Day 17 retry tests without Azure or transport calls."""

import json
from datetime import UTC, datetime
from importlib import import_module

import pytest

decision_model = import_module("01_tool_calling.first_agent")
publisher = import_module("scripts.day10.publish_decision")
offline_boundary = import_module("scripts.day15.offline_boundary")


def _serialized_publisher_event(*, event_id: str, advisory: bool = True) -> str:
    decision = decision_model.decide("messaging")
    event = publisher.build_decision_event(
        decision,
        event_id=event_id,
        occurred_at=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
    )
    event["decision"]["rationale"] = "PRIVATE-RATIONALE-SENTINEL"
    event["advisory"] = advisory
    return json.dumps(event)


def test_serialized_publisher_event_returns_only_sanitized_audit_outcome():
    serialized = _serialized_publisher_event(event_id="day15-valid-001")

    audit = offline_boundary.process_serialized_event(serialized)

    assert audit == {
        "event_id": "day15-valid-001",
        "outcome": "pass_advisory",
        "reason_code": "APPROVED_RULE_TOPIC_ADVISORY_ONLY",
        "source": "rule",
        "policy_version": "2026-10-14.v1",
    }
    assert "PRIVATE-RATIONALE-SENTINEL" not in repr(audit)
    assert "recommendation" not in audit


def test_policy_rejection_returns_sanitized_audit_outcome():
    serialized = _serialized_publisher_event(
        event_id="day15-rejected-001", advisory=False
    )

    audit = offline_boundary.process_serialized_event(serialized)

    assert audit["outcome"] == "rejected"
    assert audit["reason_code"] == "NON_ADVISORY_REJECTED"
    assert "PRIVATE-RATIONALE-SENTINEL" not in repr(audit)


def test_serialized_llm_event_stays_non_actionable_without_text_leakage():
    decision = decision_model.decide(
        "unmatched topic",
        llm=lambda _topic: "PRIVATE-LLM-RECOMMENDATION-SENTINEL",
    )
    event = publisher.build_decision_event(
        decision,
        event_id="day15-llm-001",
        occurred_at=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
    )
    event["decision"]["rationale"] = "PRIVATE-LLM-RATIONALE-SENTINEL"

    audit = offline_boundary.process_serialized_event(json.dumps(event))

    assert audit == {
        "event_id": "day15-llm-001",
        "outcome": "non_actionable",
        "reason_code": "LLM_PROVENANCE_NON_ACTIONABLE",
        "source": "llm",
        "policy_version": "2026-10-14.v1",
    }
    assert "PRIVATE-LLM-RECOMMENDATION-SENTINEL" not in repr(audit)
    assert "PRIVATE-LLM-RATIONALE-SENTINEL" not in repr(audit)


def test_repeated_event_id_returns_duplicate_audit_outcome():
    serialized = _serialized_publisher_event(event_id="day15-duplicate-001")
    seen: set[str] = set()

    first = offline_boundary.process_serialized_event(
        serialized, seen_event_ids=seen
    )
    repeated = offline_boundary.process_serialized_event(
        serialized, seen_event_ids=seen
    )

    assert first["outcome"] == "pass_advisory"
    assert repeated["outcome"] == "duplicate"
    assert repeated["reason_code"] == "DUPLICATE_EVENT_ID"
    assert repeated["event_id"] == "day15-duplicate-001"


def test_invalid_json_raises_for_transport_retry_and_dead_letter_handling():
    with pytest.raises(json.JSONDecodeError):
        offline_boundary.process_serialized_event('{"eventType":')


def test_parse_failure_can_be_retried_without_poisoning_seen_ids():
    seen: set[str] = set()
    valid_retry = _serialized_publisher_event(event_id="day17-retry-001")
    malformed = valid_retry[:-1]

    with pytest.raises(json.JSONDecodeError):
        offline_boundary.process_serialized_event(
            malformed, seen_event_ids=seen
        )

    assert seen == set()

    retry_result = offline_boundary.process_serialized_event(
        valid_retry, seen_event_ids=seen
    )
    repeated_result = offline_boundary.process_serialized_event(
        valid_retry, seen_event_ids=seen
    )

    assert retry_result["outcome"] == "pass_advisory"
    assert retry_result["event_id"] == "day17-retry-001"
    assert repeated_result["outcome"] == "duplicate"
    assert seen == {"day17-retry-001"}
