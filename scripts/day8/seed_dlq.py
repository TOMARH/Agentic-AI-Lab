import json
import os
import secrets
import sys
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage

NAMESPACE_FQDN = os.environ.get(
    "SERVICE_BUS_FQDN",
    "sb-ai-int-likwmn7js4ffw.servicebus.windows.net"
)
QUEUE_NAME = os.environ.get("SERVICE_BUS_QUEUE_NAME", "integration-events")


def generate_w3c_traceparent() -> tuple[str, str, str]:
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    traceparent = f"00-{trace_id}-{span_id}-01"
    return traceparent, trace_id, span_id


def main() -> None:
    print("=== Seeding Poison Message to Trigger DLQ Escalation ===")
    print(f"Endpoint:   {NAMESPACE_FQDN}")
    print(f"Queue:      {QUEUE_NAME}")

    traceparent, trace_id, span_id = generate_w3c_traceparent()
    order_id = f"POISON-{secrets.token_hex(4).upper()}"

    payload = {
        "event_type": "order.failed_simulation",
        "order_id": order_id,
        "simulate_poison": True,
        "amount": 999.99,
        "currency": "USD"
    }

    body = json.dumps(payload).encode("utf-8")
    credential = DefaultAzureCredential()

    with ServiceBusClient(NAMESPACE_FQDN, credential) as client:
        with client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
            msg = ServiceBusMessage(
                body=body,
                message_id=f"msg-{order_id}",
                correlation_id=f"corr-{order_id}",
                application_properties={
                    "traceparent": traceparent,
                    "Diagnostic-Id": traceparent,
                    "Source": "dlq-seeder"
                }
            )
            sender.send_messages(msg)

    print("\nPoison message sent successfully.")
    print(f"Message ID:  msg-{order_id}")
    print(f"Trace ID:    {trace_id}")
    print("With MaxDeliveryCount=5, the consumer will fail 5 times and Azure will dead-letter this message.")


if __name__ == "__main__":
    main()
