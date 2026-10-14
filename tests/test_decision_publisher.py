import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from importlib import import_module
from unittest.mock import MagicMock, Mock

import pytest

decision_model = import_module("01_tool_calling.first_agent")
publisher = import_module("scripts.day10.publish_decision")


def test_event_keeps_day9_decision_provenance_and_schema():
    decision = decision_model.decide("messaging")
    event = publisher.build_decision_event(
        decision,
        event_id="event-001",
        occurred_at=datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc),
    )

    assert event == {
        "eventType": "ArchitectureDecision.Created",
        "schemaVersion": 1,
        "advisory": True,
        "eventId": "event-001",
        "occurredAt": "2026-10-14T10:00:00Z",
        "decision": {
            "topic": "messaging",
            "recommendation": "Assume messages can be duplicated and design consumers to be idempotent.",
            "source": "rule",
            "rationale": "An exact topic matched the local architecture-principle rules.",
        },
    }


def test_event_keeps_unmatched_decision_explicit():
    event = publisher.build_decision_event(decision_model.decide("event sourcing"))

    assert event["advisory"] is True
    assert event["decision"]["source"] == "unmatched"
    assert event["decision"]["recommendation"] == "No specific principle found for this topic."


def test_llm_decisions_are_marked_advisory():
    decision = decision_model.decide("event sourcing", llm=lambda _topic: "Use immutable events.")

    assert decision.source == "llm"
    assert publisher.build_decision_event(decision)["advisory"] is True


def test_event_rejects_naive_timestamp():
    decision = decision_model.decide("api")
    naive_time = datetime.fromtimestamp(0, tz=timezone.utc).replace(tzinfo=None)

    with pytest.raises(ValueError, match="timezone-aware"):
        publisher.build_decision_event(decision, occurred_at=naive_time)


def test_publish_rejects_event_larger_than_safe_body_limit_before_authentication():
    decision = decision_model.Decision(
        topic="messaging",
        recommendation="r" * (publisher.MAX_EVENT_BODY_BYTES + 1),
        source="rule",
        rationale="test",
    )
    credential_factory = Mock()

    with pytest.raises(ValueError, match="producer limit"):
        publisher.publish_decision(
            decision,
            namespace="example.servicebus.windows.net",
            credential_factory=credential_factory,
        )

    credential_factory.assert_not_called()


def test_publish_sends_json_with_w3c_correlation_headers_and_closes_credential():
    decision = decision_model.decide("messaging")
    credential = Mock()
    sender = Mock()
    sender_context = MagicMock()
    sender_context.__enter__.return_value = sender
    client = Mock()
    client.get_queue_sender.return_value = sender_context
    client_context = MagicMock()
    client_context.__enter__.return_value = client
    client_factory = Mock(return_value=client_context)
    message_factory = Mock(return_value=object())

    event = publisher.publish_decision(
        decision,
        namespace="example.servicebus.windows.net",
        queue_name="integration-events",
        credential_factory=Mock(return_value=credential),
        client_factory=client_factory,
        message_factory=message_factory,
        now=datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc),
        trace_id="A" * 32,
        span_id="B" * 16,
    )

    client_factory.assert_called_once_with(
        fully_qualified_namespace="example.servicebus.windows.net", credential=credential
    )
    client.get_queue_sender.assert_called_once_with(queue_name="integration-events")
    sender.send_messages.assert_called_once_with(message_factory.return_value)
    message = message_factory.call_args.kwargs
    assert json.loads(message["body"]) == event
    assert message["content_type"] == "application/json"
    assert message["message_id"] == event["eventId"]
    assert message["correlation_id"] == "a" * 32
    assert message["application_properties"] == {
        "traceparent": f"00-{'a' * 32}-{'b' * 16}-01",
        "Diagnostic-Id": f"00-{'a' * 32}-{'b' * 16}-01",
    }
    sender_context.__exit__.assert_called_once()
    client_context.__exit__.assert_called_once()
    credential.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("trace_id", "span_id", "expected_match"),
    [
        ("bad", "b" * 16, "trace_id must be 32 hex chars"),
        ("a" * 32, "short", "trace_id must be 32 hex chars"),
        ("z" * 32, "b" * 16, "only hexadecimal characters"),
        ("a" * 32, "g" * 16, "only hexadecimal characters"),
        ("0" * 32, "b" * 16, "must not be all zeros"),
        ("a" * 32, "0" * 16, "must not be all zeros"),
    ],
)
def test_publish_rejects_invalid_trace_context_before_connecting(
    trace_id: str, span_id: str, expected_match: str
):
    credential_factory = Mock()

    with pytest.raises(ValueError, match=expected_match):
        publisher.publish_decision(
            decision_model.decide("api"),
            namespace="example.servicebus.windows.net",
            credential_factory=credential_factory,
            trace_id=trace_id,
            span_id=span_id,
        )

    credential_factory.assert_not_called()


def test_publish_closes_sender_client_and_credential_when_send_fails():
    decision = decision_model.decide("messaging")
    credential = Mock()
    sender = Mock()
    sender.send_messages.side_effect = RuntimeError("simulated broker send failure")
    sender_context = MagicMock()
    sender_context.__enter__.return_value = sender
    sender_context.__exit__.return_value = False

    client = Mock()
    client.get_queue_sender.return_value = sender_context
    client_context = MagicMock()
    client_context.__enter__.return_value = client
    client_context.__exit__.return_value = False

    with pytest.raises(RuntimeError, match="simulated broker send failure"):
        publisher.publish_decision(
            decision,
            namespace="example.servicebus.windows.net",
            credential_factory=Mock(return_value=credential),
            client_factory=Mock(return_value=client_context),
            message_factory=Mock(return_value=object()),
        )

    sender_context.__exit__.assert_called_once()
    client_context.__exit__.assert_called_once()
    credential.close.assert_called_once_with()


def test_publish_closes_credential_when_client_initialization_fails():
    decision = decision_model.decide("messaging")
    credential = Mock()

    with pytest.raises(RuntimeError, match="client init failure"):
        publisher.publish_decision(
            decision,
            namespace="example.servicebus.windows.net",
            credential_factory=Mock(return_value=credential),
            client_factory=Mock(side_effect=RuntimeError("client init failure")),
            message_factory=Mock(return_value=object()),
        )

    credential.close.assert_called_once_with()


def test_cli_requires_explicit_namespace(monkeypatch):
    monkeypatch.delenv("SERVICE_BUS_FQDN", raising=False)
    monkeypatch.setattr(sys, "argv", ["publish_decision", "messaging"])

    with pytest.raises(SystemExit) as exc_info:
        publisher.main()

    assert exc_info.value.code == 2


def test_cli_exits_nonzero_on_empty_topic():
    env = {**os.environ, "SERVICE_BUS_FQDN": "example.servicebus.windows.net"}
    result = subprocess.run(
        [sys.executable, "-m", "scripts.day10.publish_decision", "   "],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode != 0
    assert "topic must not be empty" in result.stderr
