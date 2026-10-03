import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import function_app

def test_missing_storage_url_returns_configuration_error(monkeypatch):
    monkeypatch.delenv("BLOB_STORAGE_ACCOUNT_URL", raising=False)

    response = function_app.BlobIdentityDemo(Mock())

    assert response.status_code == 500
    assert response.get_body().decode() == "BLOB_STORAGE_ACCOUNT_URL is not configured."


def test_lists_blobs_with_managed_identity_credential(monkeypatch):
    account_url = "https://example.blob.core.windows.net/"
    credential = object()

    monkeypatch.setenv("BLOB_STORAGE_ACCOUNT_URL", account_url)
    monkeypatch.setenv("BLOB_CONTAINER_NAME", "incoming")

    container_client = Mock()
    container_client.list_blobs.return_value = [
        SimpleNamespace(name="alpha.txt"),
        SimpleNamespace(name="beta.txt"),
    ]

    blob_service_client = Mock()
    blob_service_client.get_container_client.return_value = container_client

    credential_factory = Mock(return_value=credential)
    client_factory = Mock(return_value=blob_service_client)
    monkeypatch.setattr(function_app, "DefaultAzureCredential", credential_factory)
    monkeypatch.setattr(function_app, "BlobServiceClient", client_factory)

    response = function_app.BlobIdentityDemo(Mock())

    credential_factory.assert_called_once_with()
    client_factory.assert_called_once_with(
        account_url=account_url,
        credential=credential,
    )
    blob_service_client.get_container_client.assert_called_once_with("incoming")
    assert response.status_code == 200
    assert response.get_body().decode() == (
        "Container 'incoming' contains 2 blob(s): alpha.txt, beta.txt"
    )


def test_defaults_to_incoming_container(monkeypatch):
    monkeypatch.setenv(
        "BLOB_STORAGE_ACCOUNT_URL",
        "https://example.blob.core.windows.net/",
    )
    monkeypatch.delenv("BLOB_CONTAINER_NAME", raising=False)

    container_client = Mock()
    container_client.list_blobs.return_value = []
    blob_service_client = Mock()
    blob_service_client.get_container_client.return_value = container_client

    monkeypatch.setattr(
        function_app,
        "DefaultAzureCredential",
        Mock(return_value=object()),
    )
    monkeypatch.setattr(
        function_app,
        "BlobServiceClient",
        Mock(return_value=blob_service_client),
    )

    response = function_app.BlobIdentityDemo(Mock())

    blob_service_client.get_container_client.assert_called_once_with("incoming")
    assert response.status_code == 200
    assert response.get_body().decode() == "Container 'incoming' contains 0 blob(s): "


def test_blob_error_returns_generic_server_error(monkeypatch):
    monkeypatch.setenv(
        "BLOB_STORAGE_ACCOUNT_URL",
        "https://example.blob.core.windows.net/",
    )

    container_client = Mock()
    container_client.list_blobs.side_effect = RuntimeError("private error details")
    blob_service_client = Mock()
    blob_service_client.get_container_client.return_value = container_client

    monkeypatch.setattr(
        function_app,
        "DefaultAzureCredential",
        Mock(return_value=object()),
    )
    monkeypatch.setattr(
        function_app,
        "BlobServiceClient",
        Mock(return_value=blob_service_client),
    )

    response = function_app.BlobIdentityDemo(Mock())

    assert response.status_code == 500
    assert response.get_body().decode() == (
        "Blob access failed. Check the Function configuration and Azure permissions."
    )
    assert "private error details" not in response.get_body().decode()

def test_service_bus_consumer_logs_metadata_without_body(caplog):
    message_body = b'{"sensitive":"do-not-log"}'
    message = Mock()
    message.get_body.return_value = message_body
    message.message_id = "message-123"
    message.content_type = "application/json"

    with caplog.at_level("INFO", logger=function_app.logger.name):
        function_app.ServiceBusQueueConsumer(message)

    assert "Processed Service Bus message id=message-123" in caplog.text
    assert "content_type=application/json" in caplog.text
    assert f"bytes={len(message_body)}" in caplog.text
    assert "do-not-log" not in caplog.text


def test_service_bus_consumer_raises_on_invalid_utf8():
    message = Mock()
    message.get_body.return_value = b"\xff"

    try:
        function_app.ServiceBusQueueConsumer(message)
    except UnicodeDecodeError:
        pass
    else:
        raise AssertionError("invalid UTF-8 should fail and be retried")


def test_service_bus_consumer_idempotency_skips_duplicate(caplog):
    # Reset in-memory state for clean test isolation
    function_app.PROCESSED_MESSAGE_IDS.clear()

    message = Mock()
    message.message_id = "duplicate-msg-001"
    message.content_type = "application/json"
    message.get_body.return_value = b'{"event": "test"}'
    message.delivery_count = 1

    # First delivery - process normally
    with caplog.at_level("INFO", logger=function_app.logger.name):
        function_app.ServiceBusQueueConsumer(message)

    assert "Processed Service Bus message id=duplicate-msg-001" in caplog.text
    assert "duplicate-msg-001" in function_app.PROCESSED_MESSAGE_IDS

    # Second delivery with duplicate message_id - should skip
    message.delivery_count = 2
    with caplog.at_level("WARNING", logger=function_app.logger.name):
        function_app.ServiceBusQueueConsumer(message)

    assert "Duplicate message detected id=duplicate-msg-001 delivery_count=2. Skipping execution." in caplog.text


def test_service_bus_consumer_raises_on_simulated_poison_payload():
    function_app.PROCESSED_MESSAGE_IDS.clear()

    message = Mock()
    message.message_id = "poison-msg-999"
    message.content_type = "application/json"
    message.get_body.return_value = json.dumps({"simulate_poison": True}).encode("utf-8")
    message.delivery_count = 1

    with pytest.raises(ValueError, match="Poison message processing failed for id=poison-msg-999"):
        function_app.ServiceBusQueueConsumer(message)

    # Poison message should NOT be marked as processed
    assert "poison-msg-999" not in function_app.PROCESSED_MESSAGE_IDS


def test_service_bus_consumer_raises_on_malformed_json():
    function_app.PROCESSED_MESSAGE_IDS.clear()

    message = Mock()
    message.message_id = "malformed-json-msg"
    message.content_type = "application/json"
    message.get_body.return_value = b'{"unclosed_json": '
    message.delivery_count = 1

    with pytest.raises(json.JSONDecodeError):
        function_app.ServiceBusQueueConsumer(message)

    assert "malformed-json-msg" not in function_app.PROCESSED_MESSAGE_IDS
