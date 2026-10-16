import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import function_app


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


def test_blob_identity_demo_missing_configuration_returns_500(monkeypatch):
    monkeypatch.delenv("BLOB_STORAGE_ACCOUNT_URL", raising=False)
    response = function_app.blob_identity_demo(SimpleNamespace(params={}))

    assert response.status_code == 500
    assert response.get_body().decode("utf-8") == "BLOB_STORAGE_ACCOUNT_URL is not configured."


def test_blob_identity_demo_lists_blobs_with_managed_identity(monkeypatch):
    monkeypatch.setenv("BLOB_STORAGE_ACCOUNT_URL", "https://mockstorage.blob.core.windows.net")
    monkeypatch.setenv("BLOB_CONTAINER_NAME", "day18-input")

    fake_credential = Mock()
    monkeypatch.setattr(function_app, "DefaultAzureCredential", Mock(return_value=fake_credential))
    fake_container = Mock()
    fake_container.list_blobs.return_value = [
        SimpleNamespace(name="one.json"),
        SimpleNamespace(name="two.json"),
    ]
    fake_service = Mock()
    fake_service.get_container_client.return_value = fake_container
    mock_service_class = Mock(return_value=fake_service)
    monkeypatch.setattr(function_app, "BlobServiceClient", mock_service_class)

    response = function_app.blob_identity_demo(SimpleNamespace(params={}))

    assert response.status_code == 200
    assert response.get_body().decode("utf-8") == (
        "Container 'day18-input' contains 2 blob(s): one.json, two.json"
    )
    mock_service_class.assert_called_once_with(
        account_url="https://mockstorage.blob.core.windows.net",
        credential=fake_credential,
    )
    fake_service.get_container_client.assert_called_once_with("day18-input")


def test_blob_identity_demo_defaults_container_and_handles_blob_errors(monkeypatch):
    monkeypatch.setenv("BLOB_STORAGE_ACCOUNT_URL", "https://mockstorage.blob.core.windows.net")
    monkeypatch.delenv("BLOB_CONTAINER_NAME", raising=False)
    monkeypatch.setattr(function_app, "DefaultAzureCredential", Mock())
    fake_container = Mock()
    fake_container.list_blobs.side_effect = RuntimeError("storage unavailable")
    fake_service = Mock()
    fake_service.get_container_client.return_value = fake_container
    monkeypatch.setattr(function_app, "BlobServiceClient", Mock(return_value=fake_service))

    response = function_app.blob_identity_demo(SimpleNamespace(params={}))

    assert response.status_code == 500
    assert response.get_body().decode("utf-8") == (
        "Blob access failed. Check the Function configuration and Azure permissions."
    )
    fake_service.get_container_client.assert_called_once_with("incoming")


def test_day18_logic_app_route_contract_matches_function_and_service_bus():
    contract_path = Path(__file__).parents[2] / "docs" / "architecture" / "day18-logicapp-contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    function_contract = contract["function"]
    workflow = contract["workflow"]

    assert function_contract["route"] == function_app.BLOB_IDENTITY_DEMO_ROUTE
    assert function_contract["methods"] == list(function_app.BLOB_IDENTITY_DEMO_METHODS)
    assert function_contract["authLevel"] == "ANONYMOUS"
    assert function_app.BLOB_IDENTITY_DEMO_AUTH_LEVEL == function_app.func.AuthLevel.ANONYMOUS
    assert function_contract["storageEnvironment"] == [
        "BLOB_STORAGE_ACCOUNT_URL",
        "BLOB_CONTAINER_NAME",
    ]

    actions = workflow["actions"]
    http_action = actions["HTTP"]
    send_action = actions["Send_ServiceBus_Message"]
    assert http_action["inputs"]["method"] == function_contract["methods"][0]
    assert http_action["inputs"]["uri"].endswith(f"/api/{function_contract['route']}")
    assert http_action["inputs"]["authentication"]["audience"] == "https://management.azure.com"
    assert send_action["inputs"]["method"] == "POST"
    assert send_action["runAfter"] == {"HTTP": ["Succeeded"]}
    assert "/integration-events/messages?timeout=60" in send_action["inputs"]["uri"]


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
    fake_message.get_body.assert_not_called()
    assert function_app.PROCESSED_MESSAGE_IDS == {"msg-duplicate-test"}


def test_service_bus_consumer_retry_after_failure_is_processed_once():
    function_app.PROCESSED_MESSAGE_IDS.clear()
    fake_message = SimpleNamespace(
        message_id="msg-retry-after-failure",
        delivery_count=1,
        correlation_id=None,
        application_properties={},
        get_body=Mock(return_value=b'{"simulate_poison": true}'),
    )

    with pytest.raises(ValueError, match="Poison message delivery failure simulation"):
        function_app.service_bus_queue_consumer(fake_message)
    assert "msg-retry-after-failure" not in function_app.PROCESSED_MESSAGE_IDS

    fake_message.delivery_count = 2
    fake_message.get_body = Mock(return_value=b'{"status": "recovered"}')
    function_app.service_bus_queue_consumer(fake_message)
    fake_message.get_body.assert_called_once()
    assert "msg-retry-after-failure" in function_app.PROCESSED_MESSAGE_IDS

    fake_message.delivery_count = 3
    function_app.service_bus_queue_consumer(fake_message)
    fake_message.get_body.assert_called_once()
    assert function_app.PROCESSED_MESSAGE_IDS == {"msg-retry-after-failure"}


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
    assert context["trace_id"] is None
    assert context["parent_span_id"] is None
    assert context["correlation_id"] == "corr-cust-9988"
    assert context["trace_source"] == "correlation_id"


def test_extract_trace_context_empty():
    fake_message = SimpleNamespace(
        correlation_id=None,
        application_properties={},
    )
    context = function_app.extract_trace_context(fake_message)
    assert context["trace_id"] is None
    assert context["parent_span_id"] is None
    assert context["correlation_id"] is None
    assert context["trace_source"] == "none"

def test_extract_trace_context_amqp_bytes():
    msg = SimpleNamespace(
        application_properties={
            b"traceparent": b"00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        },
        correlation_id=None,
    )
    result = function_app.extract_trace_context(msg)
    assert result["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert result["parent_span_id"] == "00f067aa0ba902b7"
    assert result["trace_source"] == "traceparent"
    assert result["correlation_id"] is None


def test_extract_trace_context_rejects_w3c_spec_invalid_values():
    # version ff is invalid
    msg_ff = SimpleNamespace(
        application_properties={"traceparent": "ff-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
        correlation_id=None,
    )
    assert function_app.extract_trace_context(msg_ff)["trace_source"] == "none"

    # all-zeros trace_id is invalid
    msg_zeros = SimpleNamespace(
        application_properties={"traceparent": f"00-{'0'*32}-00f067aa0ba902b7-01"},
        correlation_id=None,
    )
    assert function_app.extract_trace_context(msg_zeros)["trace_source"] == "none"

    # all-zeros parent_span_id is invalid
    msg_zero_span = SimpleNamespace(
        application_properties={"traceparent": f"00-4bf92f3577b34da6a3ce929d0e0e4736-{'0'*16}-01"},
        correlation_id=None,
    )
    assert function_app.extract_trace_context(msg_zero_span)["trace_source"] == "none"


def test_extract_trace_context_correlation_id_does_not_poison_trace_id():
    msg = SimpleNamespace(
        application_properties={},
        correlation_id="ORDER-REQ-9921",
    )
    result = function_app.extract_trace_context(msg)
    assert result["trace_id"] is None
    assert result["parent_span_id"] is None
    assert result["correlation_id"] == "ORDER-REQ-9921"
    assert result["trace_source"] == "correlation_id"
