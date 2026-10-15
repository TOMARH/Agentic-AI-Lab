"""Parse serialized decision events and return sanitized Day 11 audit outcomes."""

from __future__ import annotations

import json
from collections.abc import MutableSet
from dataclasses import asdict
from importlib import import_module
from typing import Any

evaluate_decision_event = import_module("scripts.day11.policy_gate").evaluate_decision_event


def process_serialized_event(
    serialized_event: str,
    *,
    seen_event_ids: MutableSet[str] | None = None,
) -> dict[str, Any]:
    """Evaluate one JSON event and return only its sanitized audit record.

    JSON decoding errors deliberately propagate so a transport adapter can apply its
    normal retry and eventual dead-letter behavior instead of acknowledging bad input.
    """
    event = json.loads(serialized_event)
    evaluation = evaluate_decision_event(event, seen_event_ids=seen_event_ids)
    return asdict(evaluation.audit)
