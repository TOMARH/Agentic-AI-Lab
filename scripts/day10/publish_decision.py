"""Publish one Day 9 architecture decision to the existing Service Bus queue."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from importlib import import_module
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage

decision_model = import_module("01_tool_calling.first_agent")
Decision = decision_model.Decision
decide = decision_model.decide
gemini_recommendation = decision_model.gemini_recommendation

DEFAULT_NAMESPACE = "sb-ai-int-likwmn7js4ffw.servicebus.windows.net"
DEFAULT_QUEUE = "integration-events"
EVENT_TYPE = "ArchitectureDecision.Created"


def build_decision_event(
    decision: Any,
    *,
    event_id: str | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a versioned JSON-compatible event while retaining decision provenance."""
    if decision.source not in {"rule", "llm", "unmatched"}:
        raise ValueError(f"unsupported decision source: {decision.source}")

    timestamp = occurred_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("occurred_at must be timezone-aware")

    return {
        "eventType": EVENT_TYPE,
        "schemaVersion": 1,
        "eventId": event_id or uuid.uuid4().hex,
        "occurredAt": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "decision": asdict(decision),
    }


def publish_decision(
    decision: Any,
    *,
    namespace: str = DEFAULT_NAMESPACE,
    queue_name: str = DEFAULT_QUEUE,
    credential_factory: Any | None = None,
    client_factory: Any | None = None,
    message_factory: Any | None = None,
    now: datetime | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> dict[str, Any]:
    """Send one decision event using Entra credentials and return its event envelope."""
    event = build_decision_event(decision, occurred_at=now)
    trace_id = trace_id or uuid.uuid4().hex
    span_id = span_id or uuid.uuid4().hex[:16]
    if len(trace_id) != 32 or len(span_id) != 16:
        raise ValueError("trace_id must be 32 hex chars and span_id must be 16 hex chars")
    try:
        int(trace_id, 16)
        int(span_id, 16)
    except ValueError as error:
        raise ValueError("trace IDs must contain only hexadecimal characters") from error
    traceparent = f"00-{trace_id}-{span_id}-01"

    credential_factory = credential_factory or DefaultAzureCredential
    client_factory = client_factory or ServiceBusClient
    message_factory = message_factory or ServiceBusMessage
    credential = credential_factory()
    try:
        message = message_factory(
            body=json.dumps(event, ensure_ascii=False, separators=(",", ":")),
            message_id=event["eventId"],
            correlation_id=trace_id,
            content_type="application/json",
            application_properties={
                "traceparent": traceparent,
                "Diagnostic-Id": traceparent,
            },
        )
        with (
            client_factory(fully_qualified_namespace=namespace, credential=credential) as client,
            client.get_queue_sender(queue_name=queue_name) as sender,
        ):
            sender.send_messages(message)
    finally:
        close = getattr(credential, "close", None)
        if close is not None:
            close()
    return event


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic", nargs="?", default="messaging")
    parser.add_argument("--llm", action="store_true", help="Allow Gemini on an unknown topic.")
    args = parser.parse_args()

    decision = decide(args.topic, llm=gemini_recommendation if args.llm else None)
    event = publish_decision(
        decision,
        namespace=os.getenv("SERVICE_BUS_FQDN", DEFAULT_NAMESPACE),
        queue_name=os.getenv("SERVICE_BUS_QUEUE_NAME", DEFAULT_QUEUE),
    )
    print(
        f"Published event {event['eventId']} to {os.getenv('SERVICE_BUS_QUEUE_NAME', DEFAULT_QUEUE)} "
        f"(decision source: {decision.source})."
    )


if __name__ == "__main__":
    main()
