import argparse
import json
import os
import sys
from azure.identity import DefaultAzureCredential
from azure.servicebus import (
    ServiceBusClient,
    ServiceBusMessage,
    ServiceBusSubQueue,
)

NAMESPACE_FQDN = os.environ.get(
    "SERVICE_BUS_FQDN",
    "sb-ai-int-likwmn7js4ffw.servicebus.windows.net",
)
QUEUE_NAME = os.environ.get("SERVICE_BUS_QUEUE_NAME", "integration-events")


def peek_dlq(max_messages: int = 10) -> None:
    """Non-destructive inspection of the Dead-Letter Queue."""
    print(f"=== Peeking up to {max_messages} Dead-Letter Queue Messages ===")
    print(f"Endpoint: {NAMESPACE_FQDN}")
    print(f"Queue:    {QUEUE_NAME}/$DeadLetterQueue\n")

    credential = DefaultAzureCredential()
    with ServiceBusClient(NAMESPACE_FQDN, credential) as client:
        with client.get_queue_receiver(
            queue_name=QUEUE_NAME,
            sub_queue=ServiceBusSubQueue.DEAD_LETTER,
        ) as receiver:
            messages = receiver.peek_messages(max_message_count=max_messages)
            if not messages:
                print("DLQ is empty.")
                return

            for idx, msg in enumerate(messages, start=1):
                props = msg.application_properties or {}
                # Safely decode byte keys if present
                clean_props = {
                    (k.decode() if isinstance(k, bytes) else str(k)): (
                        v.decode() if isinstance(v, bytes) else str(v)
                    )
                    for k, v in props.items()
                }

                print(f"[{idx}] Message ID:            {msg.message_id}")
                print(f"    Delivery Count:        {msg.delivery_count}")
                print(f"    Dead-Letter Reason:    {msg.dead_letter_reason}")
                print(f"    Error Description:     {msg.dead_letter_error_description}")
                print(f"    Correlation ID:        {msg.correlation_id}")
                print(f"    W3C Traceparent:       {clean_props.get('traceparent')}")
                try:
                    body = b"".join(msg.body).decode("utf-8")
                    print(f"    Payload Preview:       {body[:120]}...")
                except Exception:
                    print("    Payload:               <non-utf8 bytes>")
                print("-" * 50)


def replay_dlq(max_messages: int = 5, remediate_poison: bool = False) -> None:
    """Receive from DLQ and resubmit to active queue with replay tracking."""
    print(f"=== Controlled Replay of up to {max_messages} DLQ Messages ===")
    print(f"Remediate Poison Flag: {remediate_poison}\n")

    credential = DefaultAzureCredential()
    with ServiceBusClient(NAMESPACE_FQDN, credential) as client:
        with client.get_queue_receiver(
            queue_name=QUEUE_NAME,
            sub_queue=ServiceBusSubQueue.DEAD_LETTER,
        ) as receiver, client.get_queue_sender(queue_name=QUEUE_NAME) as sender:

            messages = receiver.receive_messages(
                max_message_count=max_messages, max_wait_time=5
            )
            if not messages:
                print("No messages found in DLQ to replay.")
                return

            for msg in messages:
                body_bytes = b"".join(msg.body)
                props = dict(msg.application_properties or {})

                # If remediating simulated poison payload, patch payload
                if remediate_poison:
                    try:
                        data = json.loads(body_bytes.decode("utf-8"))
                        if isinstance(data, dict) and data.get("simulate_poison"):
                            data["simulate_poison"] = False
                            data["remediated"] = True
                            body_bytes = json.dumps(data).encode("utf-8")
                            print(f"Remediated poison flag for {msg.message_id}")
                    except Exception as err:
                        print(f"Failed to patch payload: {err}")

                # Set replay tracking metadata while preserving W3C traceparent
                replay_attempt = int(props.get("x-opt-replay-attempt", 0)) + 1
                props["x-opt-replay-attempt"] = str(replay_attempt)
                props["x-original-deadletter-reason"] = str(msg.dead_letter_reason or "MaxDeliveryCountExceeded")

                replayed_msg = ServiceBusMessage(
                    body=body_bytes,
                    message_id=msg.message_id,
                    correlation_id=msg.correlation_id,
                    application_properties=props,
                )

                # Send to active queue, then complete on DLQ
                sender.send_messages(replayed_msg)
                receiver.complete_message(msg)
                print(f"Replayed {msg.message_id} -> Active queue (Attempt: {replay_attempt})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Service Bus DLQ Manager")
    parser.add_argument("action", choices=["peek", "replay"], help="Action to execute")
    parser.add_argument("--count", type=int, default=5, help="Number of messages")
    parser.add_argument("--remediate", action="store_true", help="Clear simulate_poison flag before replay")

    args = parser.parse_args()
    if args.action == "peek":
        peek_dlq(max_messages=args.count)
    elif args.action == "replay":
        replay_dlq(max_messages=args.count, remediate_poison=args.remediate)
