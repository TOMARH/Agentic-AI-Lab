import json
import logging
import os
import re

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

app = func.FunctionApp()

# In-memory store for idempotency tracking across invocations within the process instance
PROCESSED_MESSAGE_IDS: set[str] = set()

# W3C traceparent regex: version(2 hex)-trace_id(32 hex)-parent_id(16 hex)-trace_flags(2 hex)
W3C_TRACEPARENT_PATTERN = re.compile(r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


def extract_trace_context(message: func.ServiceBusMessage) -> dict[str, str]:
    """Extract W3C trace context or correlation identifiers from message properties."""
    app_props = getattr(message, "application_properties", {}) or {}
    raw_traceparent = app_props.get("traceparent") or app_props.get("Diagnostic-Id") or ""
    correlation_id = getattr(message, "correlation_id", None) or ""

    trace_id = ""
    parent_span_id = ""

    match = W3C_TRACEPARENT_PATTERN.match(str(raw_traceparent).strip())
    if match:
        trace_id = match.group(2)
        parent_span_id = match.group(3)
    elif correlation_id:
        trace_id = str(correlation_id).strip()

    return {
        "trace_id": trace_id,
        "parent_span_id": parent_span_id,
        "raw_traceparent": str(raw_traceparent),
    }


@app.function_name(name="ServiceBusQueueConsumer")
@app.service_bus_queue_trigger(
    arg_name="message",
    queue_name="integration-events",
    connection="SERVICE_BUS_CONNECTION",
)
def service_bus_queue_consumer(message: func.ServiceBusMessage) -> None:
    message_id = message.message_id
    delivery_count = message.delivery_count

    # Extract distributed tracing correlation context
    trace_context = extract_trace_context(message)
    trace_id = trace_context["trace_id"]

    # Idempotency check: identify duplicate deliveries
    if message_id in PROCESSED_MESSAGE_IDS:
        logger.warning(
            "Duplicate message detected. Skipping processing. MessageId=%s, DeliveryCount=%d, TraceId=%s",
            message_id,
            delivery_count,
            trace_id,
        )
        return

    try:
        body_bytes = message.get_body()
        body_text = body_bytes.decode("utf-8")
        payload = json.loads(body_text)
    except UnicodeDecodeError as err:
        logger.error(
            "Poison message encountered: non-UTF-8 payload. MessageId=%s, DeliveryCount=%d, TraceId=%s, Error=%s",
            message_id,
            delivery_count,
            trace_id,
            err,
        )
        raise
    except json.JSONDecodeError as err:
        logger.error(
            "Poison message encountered: malformed JSON payload. MessageId=%s, DeliveryCount=%d, TraceId=%s, Error=%s",
            message_id,
            delivery_count,
            trace_id,
            err,
        )
        raise

    if isinstance(payload, dict) and payload.get("simulate_poison") is True:
        logger.error(
            "Simulated poison payload triggered. MessageId=%s, DeliveryCount=%d, TraceId=%s",
            message_id,
            delivery_count,
            trace_id,
        )
        raise ValueError(f"Poison message delivery failure simulation for MessageId={message_id}")

    logger.info(
        "Processed Service Bus message successfully. MessageId=%s, DeliveryCount=%d, TraceId=%s, ParentSpanId=%s",
        message_id,
        delivery_count,
        trace_context["trace_id"],
        trace_context["parent_span_id"],
    )

    # Track message ID to enforce consumer idempotency
    PROCESSED_MESSAGE_IDS.add(message_id)


@app.route(route="list-blobs", methods=["GET", "POST"], auth_level=func.AuthLevel.ANONYMOUS)
def list_blobs(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Processing list-blobs request.")
    storage_account_url = os.environ.get("STORAGE_ACCOUNT_URL")
    if not storage_account_url:
        logger.error("Missing STORAGE_ACCOUNT_URL configuration.")
        return func.HttpResponse(
            body=json.dumps({"error": "STORAGE_ACCOUNT_URL environment variable is missing"}),
            status_code=500,
            mimetype="application/json",
        )

    container_name = req.params.get("container") or "incoming"
    try:
        credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(account_url=storage_account_url, credential=credential)
        container_client = blob_service_client.get_container_client(container_name)
        blob_list = [blob.name for blob in container_client.list_blobs()]
        return func.HttpResponse(
            body=json.dumps({"container": container_name, "blobs": blob_list}),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Error accessing storage account: %s", exc)
        return func.HttpResponse(
            body=json.dumps({"error": "Failed to list blobs"}),
            status_code=500,
            mimetype="application/json",
        )