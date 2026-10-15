"""Day 14 local contract tests across the decision publisher and policy gate."""

from datetime import datetime, timezone
from importlib import import_module

decision_model = import_module("01_tool_calling.first_agent")
publisher = import_module("scripts.day10.publish_decision")
policy_gate = import_module("scripts.day11.policy_gate")


def _publisher_event(*, topic: str, event_id: str, llm=None) -> dict:
    decision = decision_model.decide(topic, llm=llm)
    return publisher.build_decision_event(
        decision,
        event_id=event_id,
        occurred_at=datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc),
    )


def test_publisher_rule_event_passes_policy_gate_as_advisory_only():
    event = _publisher_event(topic="messaging", event_id="day14-rule-001")

    result = policy_gate.evaluate_decision_event(event)

    assert event["schemaVersion"] == 1
    assert event["advisory"] is True
    assert event["decision"]["source"] == "rule"
    assert result.outcome == "pass_advisory"
    assert result.reason_code == "APPROVED_RULE_TOPIC_ADVISORY_ONLY"
    assert result.actionable is False
    assert result.authorizes_execution is False


def test_publisher_llm_event_remains_non_actionable_at_policy_gate():
    event = _publisher_event(
        topic="event sourcing",
        event_id="day14-llm-001",
        llm=lambda _topic: "Use immutable events.",
    )

    result = policy_gate.evaluate_decision_event(event)

    assert event["schemaVersion"] == 1
    assert event["decision"]["source"] == "llm"
    assert result.outcome == "non_actionable"
    assert result.reason_code == "LLM_PROVENANCE_NON_ACTIONABLE"
    assert result.actionable is False
    assert result.authorizes_execution is False


def test_malformed_publisher_event_is_rejected():
    event = _publisher_event(topic="messaging", event_id="day14-malformed-001")
    event["schemaVersion"] = "1"

    result = policy_gate.evaluate_decision_event(event)

    assert result.outcome == "rejected"
    assert result.reason_code == "UNSUPPORTED_SCHEMA_VERSION"
    assert result.actionable is False
    assert result.authorizes_execution is False


def test_publisher_event_with_non_advisory_flag_is_rejected():
    event = _publisher_event(topic="messaging", event_id="day14-non-advisory-001")
    event["advisory"] = False

    result = policy_gate.evaluate_decision_event(event)

    assert result.outcome == "rejected"
    assert result.reason_code == "NON_ADVISORY_REJECTED"
    assert result.actionable is False
    assert result.authorizes_execution is False
