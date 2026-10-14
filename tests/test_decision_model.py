import pytest
from importlib import import_module

decide = import_module("01_tool_calling.first_agent").decide


def test_known_topic_uses_local_rule_before_llm():
    def unexpected_llm(_topic: str) -> str:
        raise AssertionError("known topics must not call the LLM")

    decision = decide(" Messaging ", llm=unexpected_llm)

    assert decision.topic == "messaging"
    assert decision.source == "rule"
    assert "idempotent" in decision.recommendation


def test_unknown_topic_is_typed_unmatched_decision_without_llm():
    decision = decide("event sourcing")

    assert decision.source == "unmatched"
    assert decision.topic == "event sourcing"
    assert decision.recommendation == "No specific principle found for this topic."
    assert decision.rationale


def test_unknown_topic_uses_optional_llm_and_marks_provenance():
    calls: list[str] = []

    def fake_llm(topic: str) -> str:
        calls.append(topic)
        return "Keep events immutable."

    decision = decide("Event Sourcing", llm=fake_llm)

    assert calls == ["event sourcing"]
    assert decision.source == "llm"
    assert decision.recommendation == "Keep events immutable."


def test_empty_topic_is_rejected():
    with pytest.raises(ValueError, match="topic must not be empty"):
        decide("  ")


def test_empty_llm_answer_is_rejected():
    with pytest.raises(ValueError, match="LLM returned an empty recommendation"):
        decide("event sourcing", llm=lambda _topic: "  ")
