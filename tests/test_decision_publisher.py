import json
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

    assert event["decision"]["source"] == "unmatched"
    assert event["decision"]["recommendation"] == "No specific principle found for this topic."


def test_event_rejects_naive_timestamp():
    decision = decision_model.decide("api")
    naive_time = datetime.fromtimestamp(0, tz=timezone.utc).replace(tzinfo=None)

    with pytest.raises(ValueError, match="timezone-aware"):
        publisher.build_decision_event(decision, occurred_at=naive_time)


def test_publish_sends_json_with_trace_context_and_closes_credential():
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
        trace_id="a" * 32,
        span_id="b" * 16,
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
    credential.close.assert_called_once_with()


def test_publish_rejects_invalid_trace_context_before_connecting():
    credential_factory = Mock()

    with pytest.raises(ValueError, match="trace_id must be 32 hex chars"):
        publisher.publish_decision(
            decision_model.decide("api"),
            credential_factory=credential_factory,
            trace_id="bad",
            span_id="b" * 16,
        )

    credential_factory.assert_not_called()
