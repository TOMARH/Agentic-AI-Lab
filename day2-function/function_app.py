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

# Strict W3C traceparent regex: version 00-fe (rejecting ff), 32-hex trace-id, 16-hex parent-id, 2-hex flags
_W3C_TRACEPARENT_PATTERN = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)
_ALL_ZEROS_TRACE_ID = "0" * 32
_ALL_ZEROS_SPAN_ID = "0" * 16

def _to_str(val: object) -> str | None:
    """Safely decode bytes or convert object to string."""
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace").strip()
    return str(val).strip()


def extract_trace_context(message: object) -> dict[str, str | None]:
    """Extract and validate W3C trace context, distinguishing trace_id from correlation_id."""
    raw_props = getattr(message, "application_properties", {}) or {}

    # AMQP properties may arrive with bytes or str keys/values
    props: dict[str, str] = {}
    if isinstance(raw_props, dict):
        for k, v in raw_props.items():
            str_k = _to_str(k)
            str_v = _to_str(v)
            if str_k and str_v:
                props[str_k] = str_v

    raw_traceparent = props.get("traceparent") or props.get("Diagnostic-Id")

    if raw_traceparent:
        match = _W3C_TRACEPARENT_PATTERN.fullmatch(raw_traceparent)
        if match:
            version, trace_id, parent_span_id, _flags = match.groups()
            # Spec compliance: version 'ff' is invalid; IDs cannot be all zeros
            if (
                version != "ff"
                and trace_id != _ALL_ZEROS_TRACE_ID
                and parent_span_id != _ALL_ZEROS_SPAN_ID
            ):
                source = "traceparent" if "traceparent" in props else "Diagnostic-Id"
                return {
                    "trace_id": trace_id,
                    "parent_span_id": parent_span_id,
                    "correlation_id": None,
                    "trace_source": source,
                }

    # Fallback: correlation_id is application context, NOT a valid W3C trace ID
    raw_corr = getattr(message, "correlation_id", None)
    corr_str = _to_str(raw_corr)
    if corr_str:
        # Sanitize and cap length to prevent log-injection or cardinality explosion
        sanitized_corr = re.sub(r"[^a-zA-Z0-9_\-\.:]", "", corr_str)[:64]
        if sanitized_corr:
            return {
                "trace_id": None,
                "parent_span_id": None,
                "correlation_id": sanitized_corr,
                "trace_source": "correlation_id",
            }

    return {
        "trace_id": None,
        "parent_span_id": None,
        "correlation_id": None,
        "trace_source": "none",
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

    trace_ctx = extract_trace_context(message)
    logger.info(
        "Consuming message: ID=%s, Enqueued=%s, DeliveryCount=%s, TraceSource=%s",
            message.message_id,
            getattr(message, "enqueued_time_utc", None),
            getattr(message, "delivery_count", 1),
            trace_ctx["trace_source"],
            extra={
            "customDimensions": {
                "TraceId": trace_ctx["trace_id"],
                "ParentSpanId": trace_ctx["parent_span_id"],
                "CorrelationId": trace_ctx["correlation_id"],
                "TraceSource": trace_ctx["trace_source"],
                "MessageId": message.message_id,
                "DeliveryCount": getattr(message, "delivery_count", 1),
            }
        },
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