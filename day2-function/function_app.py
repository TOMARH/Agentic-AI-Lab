import json
import logging
import os

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient


logger = logging.getLogger(__name__)

app = func.FunctionApp()

# In-memory store for idempotency tracking across invocations within the process instance
PROCESSED_MESSAGE_IDS: set[str] = set()


@app.route(route="BlobIdentityDemo", auth_level=func.AuthLevel.FUNCTION)
def BlobIdentityDemo(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("BlobIdentityDemo function processed a request.")

    storage_account_url = os.environ.get("BLOB_STORAGE_ACCOUNT_URL")
    container_name = os.environ.get("BLOB_CONTAINER_NAME", "incoming")

    if not storage_account_url:
        return func.HttpResponse(
            "BLOB_STORAGE_ACCOUNT_URL is not configured.",
            status_code=500,
        )

    try:
        credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(
            account_url=storage_account_url,
            credential=credential,
        )

        container_client = blob_service_client.get_container_client(container_name)

        blobs = [blob.name for blob in container_client.list_blobs()]

        return func.HttpResponse(
            f"Container '{container_name}' contains {len(blobs)} blob(s): "
            + ", ".join(blobs),
            status_code=200,
        )

    except Exception:
        logger.exception("Blob access failed.")
        return func.HttpResponse(
            "Blob access failed. Check the Function configuration and Azure permissions.",
            status_code=500,
        )


@app.function_name(name="ServiceBusQueueConsumer")
@app.service_bus_queue_trigger(
    arg_name="message",
    queue_name="integration-events",
    connection="ServiceBusConnection",
)
def ServiceBusQueueConsumer(message: func.ServiceBusMessage) -> None:
    """Consume a queue message with idempotency tracking and poison payload detection."""
    msg_id = message.message_id or "unknown"
    delivery_count = getattr(message, "delivery_count", 1)

    # 1. Idempotency Check: Short-circuit if already processed
    if msg_id != "unknown" and msg_id in PROCESSED_MESSAGE_IDS:
        logger.warning(
            "Duplicate message detected id=%s delivery_count=%s. Skipping execution.",
            msg_id,
            delivery_count,
        )
        return

    # 2. Decode and Validate UTF-8
    body_bytes = message.get_body()
    try:
        decoded_text = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        logger.error("Poison payload: Message id=%s is not valid UTF-8.", msg_id)
        raise

    # 3. Structured Payload Parsing & Controlled Poison Validation
    if message.content_type == "application/json" or decoded_text.strip().startswith("{"):
        try:
            payload = json.loads(decoded_text)
            if isinstance(payload, dict) and payload.get("simulate_poison") is True:
                logger.error(
                    "Simulated poison payload encountered for message id=%s delivery_count=%s.",
                    msg_id,
                    delivery_count,
                )
                raise ValueError(f"Poison message processing failed for id={msg_id}")
        except json.JSONDecodeError:
            logger.error("Poison payload: JSON malformed in message id=%s.", msg_id)
            raise

    # 4. Mark Processed for Idempotency
    if msg_id != "unknown":
        PROCESSED_MESSAGE_IDS.add(msg_id)

    logger.info(
        "Processed Service Bus message id=%s content_type=%s bytes=%d delivery_count=%s",
        msg_id,
        message.content_type,
        len(body_bytes),
        delivery_count,
    )
