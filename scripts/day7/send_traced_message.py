import json
import os
import sys
import uuid
from datetime import datetime, timezone

from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage


def main() -> None:
    fully_qualified_namespace = os.environ.get(
        "SERVICE_BUS_FQDN", "sb-ai-int-likwmn7js4ffw.servicebus.windows.net"
    )
    queue_name = os.environ.get("SERVICE_BUS_QUEUE", "integration-events")

    trace_id = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else uuid.uuid4().hex.lower()
    span_id = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else uuid.uuid4().hex[:16].lower()
    traceparent = f"00-{trace_id}-{span_id}-01"

    print("=== Sending Traced Service Bus Message (Day 7) ===")
    print(f"Endpoint:        {fully_qualified_namespace}")
    print(f"Queue:           {queue_name}")
    print(f"W3C Traceparent: {traceparent}")
    print(f"Trace ID:        {trace_id}")
    print(f"Span ID:         {span_id}")
    print()

    payload = {
        "eventType": "IntegrationEvent.OrderSubmitted",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "day7-distributed-tracing-test",
        "traceparent": traceparent,
    }

    message = ServiceBusMessage(
        body=json.dumps(payload),
        application_properties={
            "traceparent": traceparent,
            "Diagnostic-Id": traceparent,
        },
        correlation_id=trace_id,
    )

    credential = DefaultAzureCredential()
    with ServiceBusClient(fully_qualified_namespace=fully_qualified_namespace, credential=credential) as client:
        with client.get_queue_sender(queue_name=queue_name) as sender:
            sender.send_messages(message)

    print("Message dispatched successfully with Entra ID and W3C traceparent properties.")
    print()
    print("=== KQL Query for Azure Monitor / Log Analytics ===")
    print(f"""AppTraces
| where Message contains "{trace_id}"
| project TimeGenerated, Message, SeverityLevel, OperationId = operation_Id
| order by TimeGenerated desc""")


if __name__ == "__main__":
    main()
