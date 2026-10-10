import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.day8.dlq_manager import peek_dlq, replay_dlq


@pytest.fixture
def mock_servicebus():
    """Mock ServiceBusClient context manager and child receivers/senders."""
    with patch("scripts.day8.dlq_manager.ServiceBusClient") as mock_client_cls:
        client_instance = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = client_instance

        receiver_instance = MagicMock()
        client_instance.get_queue_receiver.return_value.__enter__.return_value = receiver_instance

        sender_instance = MagicMock()
        client_instance.get_queue_sender.return_value.__enter__.return_value = sender_instance

        yield {
            "client": client_instance,
            "receiver": receiver_instance,
            "sender": sender_instance,
        }


def test_peek_dlq_empty(mock_servicebus, capsys):
    """Peek should report empty when no messages are returned."""
    mock_servicebus["receiver"].peek_messages.return_value = []

    peek_dlq(max_messages=5)

    captured = capsys.readouterr()
    assert "DLQ is empty." in captured.out
    mock_servicebus["receiver"].peek_messages.assert_called_once_with(max_message_count=5)


def test_peek_dlq_with_messages(mock_servicebus, capsys):
    """Peek should display message properties, error descriptions, and W3C traceparent."""
    msg = MagicMock()
    msg.message_id = "msg-TEST-101"
    msg.delivery_count = 5
    msg.dead_letter_reason = "MaxDeliveryCountExceeded"
    msg.dead_letter_error_description = "Message could not be consumed."
    msg.correlation_id = "corr-101"
    msg.application_properties = {
        b"traceparent": b"00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    }
    msg.body = [b'{"event": "test"}']

    mock_servicebus["receiver"].peek_messages.return_value = [msg]

    peek_dlq(max_messages=1)

    captured = capsys.readouterr()
    assert "msg-TEST-101" in captured.out
    assert "MaxDeliveryCountExceeded" in captured.out
    assert "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01" in captured.out


def test_replay_dlq_remediate_flag(mock_servicebus):
    """Replay with remediation should mutate payload, increment replay metadata, and complete message."""
    msg = MagicMock()
    msg.message_id = "msg-POISON-123"
    msg.correlation_id = "corr-123"
    msg.dead_letter_reason = "MaxDeliveryCountExceeded"
    msg.application_properties = {
        "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
        "x-opt-replay-attempt": "1",
    }
    original_payload = {"order_id": "123", "simulate_poison": True}
    msg.body = [json.dumps(original_payload).encode("utf-8")]

    mock_servicebus["receiver"].receive_messages.return_value = [msg]

    replay_dlq(max_messages=1, remediate_poison=True)

    assert mock_servicebus["sender"].send_messages.call_count == 1
    sent_msg = mock_servicebus["sender"].send_messages.call_args[0][0]

    sent_payload = json.loads(b"".join(sent_msg.body).decode("utf-8"))
    assert sent_payload["simulate_poison"] is False
    assert sent_payload["remediated"] is True

    props = sent_msg.application_properties
    assert props["x-opt-replay-attempt"] == "2"
    assert props["x-original-deadletter-reason"] == "MaxDeliveryCountExceeded"
    assert props["traceparent"] == "00-11111111111111111111111111111111-2222222222222222-01"

    mock_servicebus["receiver"].complete_message.assert_called_once_with(msg)
