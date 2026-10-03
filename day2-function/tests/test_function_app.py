import json
from types import SimpleNamespace
from unittest.mock import Mock

import function_app
import pytest


def test_missing_storage_url_returns_configuration_error(monkeypatch):
    monkeypatch.delenv("STORAGE_ACCOUNT_URL", raising=False)
    req = SimpleNamespace(params={})

    response = function_app.list_blobs(req)

    assert response.status_code == 500
    payload = json.loads(response.get_body().decode("utf-8"))
    assert payload["error"] == "STORAGE_ACCOUNT_URL environment variable is missing"


def test_lists_blobs_with_managed_identity_credential(monkeypatch):
    monkeypatch.setenv("STORAGE_ACCOUNT_URL", "https://mockstorage.blob.core.windows.net")

    fake_credential = Mock()
    monkeypatch.setattr(function_app, "DefaultAzureCredential", Mock(return_value=fake_credential))

    fake_blob = SimpleNamespace(name="incoming-file.json")
    fake_container_client = Mock()
    fake_container_client.list_blobs.return_value = [fake_blob]

    fake_blob_service_client = Mock()
    fake_blob_service_client.get_container_client.return_value = fake_container_client

    mock_blob_client_class = Mock(return_value=fake_blob_service_client)
    monkeypatch.setattr(function_app, "BlobServiceClient", mock_blob_client_class)

    req = SimpleNamespace(params={"container": "raw-data"})
    response = function_app.list_blobs(req)

    assert response.status_code == 200
    mock_blob_client_class.assert_called_once_with(
        account_url="https://mockstorage.blob.core.windows.net",
        credential=fake_credential,
    )
    fake_blob_service_client.get_container_client.assert_called_once_with("raw-data")
    payload = json.loads(response.get_body().decode("utf-8"))
    assert payload == {"container": "raw-data", "blobs": ["incoming-file.json"]}


def test_defaults_to_incoming_container(monkeypatch):
    monkeypatch.setenv("STORAGE_ACCOUNT_URL", "https://mockstorage.blob.core.windows.net")
    monkeypatch.setattr(function_app, "DefaultAzureCredential", Mock())

    fake_container_client = Mock()
    fake_container_client.list_blobs.return_value = []
    fake_blob_service_client = Mock()
    fake_blob_service_client.get_container_client.return_value = fake_container_client
    monkeypatch.setattr(function_app, "BlobServiceClient", Mock(return_value=fake_blob_service_client))

    req = SimpleNamespace(params={})
    response = function_app.list_blobs(req)

    assert response.status_code == 200
    fake_blob_service_client.get_container_client.assert_called_once_with("incoming")


def test_blob_error_returns_generic_server_error(monkeypatch):
    monkeypatch.setenv("STORAGE_ACCOUNT_URL", "https://mockstorage.blob.core.windows.net")
    monkeypatch.setattr(function_app, "DefaultAzureCredential", Mock())

    fake_container_client = Mock()
    fake_container_client.list_blobs.side_effect = RuntimeError("Storage connection refused")
    fake_blob_service_client = Mock()
    fake_blob_service_client.get_container_client.return_value = fake_container_client
    monkeypatch.setattr(function_app, "BlobServiceClient", Mock(return_value=fake_blob_service_client))

    req = SimpleNamespace(params={})
    response = function_app.list_blobs(req)

    assert response.status_code == 500
    payload = json.loads(response.get_body().decode("utf-8"))
    assert payload["error"] == "Failed to list blobs"


def test_service_bus_consumer_logs_metadata_without_body():
    function_app.PROCESSED_MESSAGE_IDS.clear()
    fake_message = SimpleNamespace(
        message_id="msg-12345",
        delivery_count=1,
        correlation_id=None,
        application_properties={},
        get_body=lambda: b'{"status": "ok"}',
    )

    function_app.service_bus_queue_consumer(fake_message)
    assert "msg-12345" in function_app.PROCESSED_MESSAGE_IDS


def test_service_bus_consumer_raises_on_invalid_utf8():
    function_app.PROCESSED_MESSAGE_IDS.clear()
    fake_message = SimpleNamespace(
        message_id="msg-poison-utf8",
        delivery_count=1,
        correlation_id=None,
        application_properties={},
        get_body=lambda: b"\x80abc",
    )

    with pytest.raises(UnicodeDecodeError):
        function_app.service_bus_queue_consumer(fake_message)
    assert "msg-poison-utf8" not in function_app.PROCESSED_MESSAGE_IDS


def test_service_bus_consumer_idempotency_skips_duplicate():
    function_app.PROCESSED_MESSAGE_IDS.clear()
    fake_message = SimpleNamespace(
        message_id="msg-duplicate-test",
        delivery_count=1,
        correlation_id=None,
        application_properties={},
        get_body=lambda: b'{"status": "ok"}',
    )

    function_app.service_bus_queue_consumer(fake_message)
    assert "msg-duplicate-test" in function_app.PROCESSED_MESSAGE_IDS

    # Duplicate run with incremented delivery_count
    fake_message.delivery_count = 2
    fake_message.get_body = Mock(side_effect=AssertionError("Should not parse body on duplicate"))
    function_app.service_bus_queue_consumer(fake_message)


def test_service_bus_consumer_raises_on_simulated_poison_payload():
    function_app.PROCESSED_MESSAGE_IDS.clear()
    fake_message = SimpleNamespace(
        message_id="msg-simulated-poison",
        delivery_count=1,
        correlation_id=None,
        application_properties={},
        get_body=lambda: b'{"simulate_poison": true, "reason": "bad payload"}',
    )

    with pytest.raises(ValueError, match="Poison message delivery failure simulation"):
        function_app.service_bus_queue_consumer(fake_message)
    assert "msg-simulated-poison" not in function_app.PROCESSED_MESSAGE_IDS


def test_service_bus_consumer_raises_on_malformed_json():
    function_app.PROCESSED_MESSAGE_IDS.clear()
    fake_message = SimpleNamespace(
        message_id="msg-bad-json",
        delivery_count=1,
        correlation_id=None,
        application_properties={},
        get_body=lambda: b'{"unclosed_json": true',
    )

    with pytest.raises(json.JSONDecodeError):
        function_app.service_bus_queue_consumer(fake_message)
    assert "msg-bad-json" not in function_app.PROCESSED_MESSAGE_IDS


def test_extract_trace_context_w3c_traceparent():
    fake_message = SimpleNamespace(
        correlation_id=None,
        application_properties={
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        },
    )
    context = function_app.extract_trace_context(fake_message)
    assert context["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert context["parent_span_id"] == "00f067aa0ba902b7"


def test_extract_trace_context_correlation_id_fallback():
    fake_message = SimpleNamespace(
        correlation_id="corr-cust-9988",
        application_properties={},
    )
    context = function_app.extract_trace_context(fake_message)
    assert context["trace_id"] == "corr-cust-9988"
    assert context["parent_span_id"] == ""


def test_extract_trace_context_empty():
    fake_message = SimpleNamespace(
        correlation_id=None,
        application_properties={},
    )
    context = function_app.extract_trace_context(fake_message)
    assert context["trace_id"] == ""
    assert context["parent_span_id"] == ""