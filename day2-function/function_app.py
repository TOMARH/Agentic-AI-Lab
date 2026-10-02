import logging
import os

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

app = func.FunctionApp()


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
    """Consume a queue message; leave business payloads out of application logs."""
    body = message.get_body()
    # Decode to fail and retry malformed text messages; successful returns are
    # completed by the Functions Service Bus extension's auto-complete behavior.
    body.decode("utf-8")
    logger.info(
        "Processed Service Bus message id=%s content_type=%s bytes=%d",
        message.message_id,
        message.content_type,
        len(body),
    )
