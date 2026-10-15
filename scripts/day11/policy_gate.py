"""Validate Day 10 decision events and return deterministic, non-executing policy outcomes."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, MutableSet
from dataclasses import asdict, dataclass
from importlib import import_module
from typing import Any, Literal

decision_model = import_module("01_tool_calling.first_agent")
PRINCIPLES: dict[str, str] = decision_model.PRINCIPLES
decide = decision_model.decide
publish_module = import_module("scripts.day10.publish_decision")
build_decision_event = publish_module.build_decision_event

POLICY_VERSION = "2026-10-14.v1"
SUPPORTED_EVENT_TYPE = "ArchitectureDecision.Created"
SUPPORTED_SCHEMA_VERSION = 1
VALID_SOURCES = frozenset({"rule", "llm", "unmatched"})
ALLOWED_RULE_TOPICS = frozenset(PRINCIPLES.keys())
EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

PolicyOutcomeStatus = Literal["pass_advisory", "non_actionable", "duplicate", "rejected"]
ReasonCode = Literal[
    "APPROVED_RULE_TOPIC_ADVISORY_ONLY",
    "RULE_RECOMMENDATION_MISMATCH",
    "UNAPPROVED_RULE_TOPIC",
    "LLM_PROVENANCE_NON_ACTIONABLE",
    "UNMATCHED_TOPIC_NON_ACTIONABLE",
    "DUPLICATE_EVENT_ID",
    "INVALID_ENVELOPE",
    "UNSUPPORTED_EVENT_TYPE",
    "UNSUPPORTED_SCHEMA_VERSION",
    "MISSING_EVENT_ID",
    "INVALID_EVENT_ID",
    "NON_ADVISORY_REJECTED",
    "INVALID_DECISION_PAYLOAD",
    "INVALID_DECISION_SOURCE",
]


@dataclass(frozen=True)
class AuditRecord:
    """Structured audit record omitting untrusted recommendation and rationale text."""

    event_id: str
    outcome: PolicyOutcomeStatus
    reason_code: ReasonCode
    source: str
    policy_version: str


@dataclass(frozen=True)
class PolicyEvaluation:
    """Typed, deterministic policy gate evaluation result."""

    event_id: str
    outcome: PolicyOutcomeStatus
    reason_code: ReasonCode
    source: str
    policy_version: str
    actionable: Literal[False]
    authorizes_execution: Literal[False]
    notice: str
    audit: AuditRecord


def _result(
    *,
    event_id: str,
    outcome: PolicyOutcomeStatus,
    reason_code: ReasonCode,
    source: str,
    notice: str,
) -> PolicyEvaluation:
    audit = AuditRecord(
        event_id=event_id,
        outcome=outcome,
        reason_code=reason_code,
        source=source,
        policy_version=POLICY_VERSION,
    )
    return PolicyEvaluation(
        event_id=event_id,
        outcome=outcome,
        reason_code=reason_code,
        source=source,
        policy_version=POLICY_VERSION,
        actionable=False,
        authorizes_execution=False,
        notice=notice,
        audit=audit,
    )


def evaluate_decision_event(
    event: Mapping[str, Any],
    *,
    seen_event_ids: MutableSet[str] | None = None,
) -> PolicyEvaluation:
    """Evaluate a Day 10 decision event envelope against the local policy gate.

    Every outcome keeps `actionable=False` and `authorizes_execution=False`.
    Recommendation and rationale text are never copied into the returned audit record.
    """
    if not isinstance(event, Mapping):
        return _result(
            event_id="<invalid>",
            outcome="rejected",
            reason_code="INVALID_ENVELOPE",
            source="unknown",
            notice="Rejected: event envelope must be a mapping; does not authorize execution.",
        )

    raw_event_id = event.get("eventId")

    if raw_event_id is None:
        return _result(
            event_id="<missing>",
            outcome="rejected",
            reason_code="MISSING_EVENT_ID",
            source="unknown",
            notice="Rejected: eventId is required; does not authorize execution.",
        )

    if (
        not isinstance(raw_event_id, str)
        or EVENT_ID_PATTERN.fullmatch(raw_event_id) is None
    ):
        return _result(
            event_id="<invalid>",
            outcome="rejected",
            reason_code="INVALID_EVENT_ID",
            source="unknown",
            notice=(
                "Rejected: eventId must contain 1–128 ASCII letters, digits, "
                "periods, underscores, colons, or hyphens; does not authorize execution."
            ),
        )

    event_id = raw_event_id
    safe_event_id = event_id

    raw_decision = event.get("decision")
    raw_source = raw_decision.get("source") if isinstance(raw_decision, Mapping) else None
    safe_source = (
        raw_source if isinstance(raw_source, str) and raw_source in VALID_SOURCES else "unknown"
    )

    if event.get("eventType") != SUPPORTED_EVENT_TYPE:
        return _result(
            event_id=safe_event_id,
            outcome="rejected",
            reason_code="UNSUPPORTED_EVENT_TYPE",
            source=safe_source,
            notice="Rejected: unsupported eventType; does not authorize execution.",
        )

    schema_version = event.get("schemaVersion")
    if (
        type(schema_version) is not int
        or schema_version != SUPPORTED_SCHEMA_VERSION
    ):
        return _result(
            event_id=safe_event_id,
            outcome="rejected",
            reason_code="UNSUPPORTED_SCHEMA_VERSION",
            source=safe_source,
            notice="Rejected: unsupported schemaVersion; does not authorize execution.",
        )

    if event.get("advisory") is not True:
        return _result(
            event_id=safe_event_id,
            outcome="rejected",
            reason_code="NON_ADVISORY_REJECTED",
            source=safe_source,
            notice="Rejected: advisory flag must be True; does not authorize execution.",
        )

    if not isinstance(raw_decision, Mapping):
        return _result(
            event_id=safe_event_id,
            outcome="rejected",
            reason_code="INVALID_DECISION_PAYLOAD",
            source="unknown",
            notice="Rejected: decision payload must be a mapping; does not authorize execution.",
        )

    if not isinstance(raw_source, str) or raw_source not in VALID_SOURCES:
        return _result(
            event_id=safe_event_id,
            outcome="rejected",
            reason_code="INVALID_DECISION_SOURCE",
            source="unknown",
            notice="Rejected: decision.source is invalid; does not authorize execution.",
        )

    raw_topic = raw_decision.get("topic")
    normalized_topic = raw_topic.strip().casefold() if isinstance(raw_topic, str) else ""
    if not normalized_topic:
        return _result(
            event_id=safe_event_id,
            outcome="rejected",
            reason_code="INVALID_DECISION_PAYLOAD",
            source=raw_source,
            notice="Rejected: decision.topic must be a non-empty string; does not authorize execution.",
        )

    if seen_event_ids is not None:
        if event_id in seen_event_ids:
            return _result(
                event_id=event_id,
                outcome="duplicate",
                reason_code="DUPLICATE_EVENT_ID",
                source=raw_source,
                notice=(
                    "Duplicate eventId suppressed in local in-memory session; "
                    "does not authorize execution."
                ),
            )
        seen_event_ids.add(event_id)

    if raw_source == "llm":
        return _result(
            event_id=event_id,
            outcome="non_actionable",
            reason_code="LLM_PROVENANCE_NON_ACTIONABLE",
            source="llm",
            notice=(
                "Non-actionable: LLM-sourced suggestion is untrusted advisory text "
                "and does not authorize execution."
            ),
        )

    if raw_source == "unmatched":
        return _result(
            event_id=event_id,
            outcome="non_actionable",
            reason_code="UNMATCHED_TOPIC_NON_ACTIONABLE",
            source="unmatched",
            notice="Non-actionable: topic has no matched rule and does not authorize execution.",
        )

    if normalized_topic not in ALLOWED_RULE_TOPICS:
        return _result(
            event_id=event_id,
            outcome="non_actionable",
            reason_code="UNAPPROVED_RULE_TOPIC",
            source="rule",
            notice=(
                "Non-actionable: rule source topic is not in the approved local policy allowlist "
                "and does not authorize execution."
            ),
        )

    expected_recommendation = PRINCIPLES[normalized_topic]
    raw_recommendation = raw_decision.get("recommendation")
    if (
        not isinstance(raw_recommendation, str)
        or raw_recommendation != expected_recommendation
    ):
        return _result(
            event_id=event_id,
            outcome="non_actionable",
            reason_code="RULE_RECOMMENDATION_MISMATCH",
            source="rule",
            notice=(
                "Non-actionable: rule recommendation does not match the approved catalog entry; "
                "does not authorize execution."
            ),
        )


    return _result(
        event_id=event_id,
        outcome="pass_advisory",
        reason_code="APPROVED_RULE_TOPIC_ADVISORY_ONLY",
        source="rule",
        notice="Advisory policy check passed for cataloged rule topic; does not authorize execution.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic", nargs="?", default="messaging")
    args = parser.parse_args()

    decision = decide(args.topic)
    event = build_decision_event(decision)
    evaluation = evaluate_decision_event(event, seen_event_ids=set())
    print(json.dumps(asdict(evaluation.audit), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
