import logging
import os

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()


@app.route(route="BlobIdentityDemo", auth_level=func.AuthLevel.FUNCTION)
def BlobIdentityDemo(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("BlobIdentityDemo function processed a request.")

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
        logging.exception("Blob access failed.")
        return func.HttpResponse(
            "Blob access failed. Check the Function configuration and Azure permissions.",
            status_code=500,
        )
