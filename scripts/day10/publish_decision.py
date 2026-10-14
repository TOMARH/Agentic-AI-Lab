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

DEFAULT_QUEUE = "integration-events"
EVENT_TYPE = "ArchitectureDecision.Created"
MAX_EVENT_BODY_BYTES = 240 * 1024
_ALL_ZEROS_TRACE_ID = "0" * 32
_ALL_ZEROS_SPAN_ID = "0" * 16


def _build_w3c_correlation_headers(
    trace_id: str | None = None,
    span_id: str | None = None,
) -> tuple[str, str]:
    """Validate or generate W3C-formatted correlation identifiers (no active OTel span)."""
    resolved_trace_id = (trace_id if trace_id is not None else uuid.uuid4().hex).lower()
    resolved_span_id = (span_id if span_id is not None else uuid.uuid4().hex[:16]).lower()

    if len(resolved_trace_id) != 32 or len(resolved_span_id) != 16:
        raise ValueError("trace_id must be 32 hex chars and span_id must be 16 hex chars")
    try:
        int(resolved_trace_id, 16)
        int(resolved_span_id, 16)
    except ValueError as error:
        raise ValueError("trace IDs must contain only hexadecimal characters") from error

    if resolved_trace_id == _ALL_ZEROS_TRACE_ID or resolved_span_id == _ALL_ZEROS_SPAN_ID:
        raise ValueError("trace_id and span_id must not be all zeros")

    return resolved_trace_id, f"00-{resolved_trace_id}-{resolved_span_id}-01"


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
        "advisory": True,
        "eventId": event_id or uuid.uuid4().hex,
        "occurredAt": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "decision": asdict(decision),
    }


def publish_decision(
    decision: Any,
    *,
    namespace: str,
    queue_name: str = DEFAULT_QUEUE,
    credential_factory: Any | None = None,
    client_factory: Any | None = None,
    message_factory: Any | None = None,
    now: datetime | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> dict[str, Any]:
    """Send one decision event with Entra credentials and W3C-formatted correlation headers."""
    event = build_decision_event(decision, occurred_at=now)
    correlation_trace_id, traceparent = _build_w3c_correlation_headers(trace_id, span_id)
    body = _serialize_event(event)

    credential_factory = credential_factory or DefaultAzureCredential
    client_factory = client_factory or ServiceBusClient
    message_factory = message_factory or ServiceBusMessage
    credential = credential_factory()
    try:
        message = message_factory(
            body=body,
            message_id=event["eventId"],
            correlation_id=correlation_trace_id,
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


def _serialize_event(event: dict[str, Any]) -> str:
    """Serialize a compact UTF-8 JSON event within the producer's safety limit."""
    body = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    if len(body.encode("utf-8")) > MAX_EVENT_BODY_BYTES:
        raise ValueError(f"event body exceeds the {MAX_EVENT_BODY_BYTES}-byte producer limit")
    return body


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic", nargs="?", default="messaging")
    parser.add_argument("--llm", action="store_true", help="Allow Gemini on an unknown topic.")
    args = parser.parse_args()

    namespace = os.getenv("SERVICE_BUS_FQDN")
    if not namespace:
        parser.error("Set SERVICE_BUS_FQDN to the intended namespace hostname before publishing.")

    queue_name = os.getenv("SERVICE_BUS_QUEUE_NAME", DEFAULT_QUEUE)
    decision = decide(args.topic, llm=gemini_recommendation if args.llm else None)
    event = publish_decision(
        decision,
        namespace=namespace,
        queue_name=queue_name,
    )
    print(
        f"Published event {event['eventId']} to {queue_name} "
        f"(decision source: {decision.source})."
    )


if __name__ == "__main__":
    main()
