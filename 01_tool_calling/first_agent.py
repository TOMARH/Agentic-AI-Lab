"""A local architecture decision lab with an optional Gemini fallback."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Callable, Literal

DecisionSource = Literal["rule", "llm", "unmatched"]


@dataclass(frozen=True)
class Decision:
    """A typed, inspectable decision returned by the local decision model."""

    topic: str
    recommendation: str
    source: DecisionSource
    rationale: str


PRINCIPLES: dict[str, str] = {
    "microservices": "Prefer independently deployable services with clear business boundaries.",
    "api": "Design APIs around stable contracts and explicit ownership.",
    "messaging": "Assume messages can be duplicated and design consumers to be idempotent.",
}


def decide(topic: str, *, llm: Callable[[str], str] | None = None) -> Decision:
    """Use deterministic rules first; consult the injected LLM only on a miss."""
    normalized_topic = topic.strip().casefold()
    if not normalized_topic:
        raise ValueError("topic must not be empty")

    if normalized_topic in PRINCIPLES:
        return Decision(
            topic=normalized_topic,
            recommendation=PRINCIPLES[normalized_topic],
            source="rule",
            rationale="An exact topic matched the local architecture-principle rules.",
        )

    if llm is not None:
        recommendation = llm(normalized_topic).strip()
        if not recommendation:
            raise ValueError("LLM returned an empty recommendation")
        return Decision(
            topic=normalized_topic,
            recommendation=recommendation,
            source="llm",
            rationale="No local rule matched; the explicitly enabled LLM supplied a suggestion.",
        )

    return Decision(
        topic=normalized_topic,
        recommendation="No specific principle found for this topic.",
        source="unmatched",
        rationale="No local rule matched and no LLM fallback was enabled.",
    )


def gemini_recommendation(topic: str) -> str:
    """Call Gemini on demand; importing this module never requires a key or network."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY to enable the optional Gemini fallback.")

    from google import genai

    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(
        model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        input=(
            "Give one concise software architecture principle for this topic. "
            "Return a recommendation, not code. Topic: " + topic
        ),
    )
    return interaction.output_text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic", nargs="?", default="messaging")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Allow Gemini to suggest a recommendation when no local rule matches.",
    )
    args = parser.parse_args()
    decision = decide(args.topic, llm=gemini_recommendation if args.llm else None)
    print(f"Topic: {decision.topic}\nSource: {decision.source}\n")
    print(decision.recommendation)
    print(f"\nRationale: {decision.rationale}")


if __name__ == "__main__":
    main()
