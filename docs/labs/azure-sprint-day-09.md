# Azure sprint — Day 9: Local decision model and typed decisions

## 1. Objective

Explore a small decision model locally: deterministic rules for known topics, a typed result that carries recommendation provenance, and an optional Gemini fallback for unknown topics. The exercise uses no Azure resources and makes no Azure runtime claims.

## 2. Architecture

```text
CLI topic
   |
   v
decide(topic)
   | exact local rule? -- yes --> Decision(source="rule")
   |
   no
   | -- --llm explicitly enabled? -- yes --> Gemini -> Decision(source="llm")
   |                                      no
   +---------------------------------------> Decision(source="unmatched")
```

`Decision` is an immutable dataclass with `topic`, `recommendation`, `source`, and `rationale`. The model checks local rules first. The Gemini callable is injected, invoked only for an unmatched topic, and imported lazily; normal imports and rule-only runs need neither a key nor network access.

## 3. Core design decisions and alternatives

1. **Rules first:** exact normalized topic matches are deterministic and do not call the model, even if the optional fallback is enabled. Alternatives include always calling an LLM, which adds latency, cost, and variability to known decisions.
2. **Typed decisions:** the dataclass exposes provenance (`rule`, `llm`, or `unmatched`) alongside the recommendation and rationale. Returning plain strings would hide the decision path from callers and reviewers.
3. **Explicit optional LLM:** Gemini is only enabled with `--llm` and only used for an unknown topic. Without that flag the result is explicitly `unmatched`. This preserves offline behavior and makes the external model boundary visible.
4. **Suggestions, not authority:** LLM output is not validated against policy and is not suitable as an authorization, safety, or production control decision. A future policy-sensitive use would need constrained outputs, validation, human review, and audit controls.

## 4. Configuration and trust boundary

| Setting | Required | Purpose |
|---|---:|---|
| `GEMINI_API_KEY` | Only for `--llm` on an unknown topic | Authenticates the optional Gemini request; never store the value in source or lab notes. |
| `GEMINI_MODEL` | No | Optional model override; defaults to `gemini-3.6-flash`, matching the existing Gemini example. |

The local rules run without credentials. The optional Gemini request sends the topic and a short instruction to the configured model provider. The recommendation is model-generated text and must be treated as untrusted input.

## 5. Local validation

These checks exercise rule selection, typed provenance, optional fallback injection, and invalid inputs without making a network request:

```powershell
python -m pytest tests/test_decision_model.py -v
python 01_tool_calling/first_agent.py messaging
python 01_tool_calling/first_agent.py "event sourcing"
```

Expected outcomes: `messaging` returns source `rule`; `event sourcing` without `--llm` returns source `unmatched`. The test suite injects a fake fallback to prove unknown topics can return source `llm` without calling Gemini.

To opt in to the external API manually, configure `GEMINI_API_KEY` in the local environment and run:

```powershell
python 01_tool_calling/first_agent.py "event sourcing" --llm
```

No live Gemini call is required for local validation, and none is represented as executed by this lab record.

## 6. Operational risks and limitations

- The rules use exact topic keys after trimming and case-folding; synonyms and fuzzy matching are not implemented.
- The optional provider call has external availability, latency, and cost considerations. There is no retry, timeout policy, response schema, or content filtering in this introductory example.
- A dataclass makes the result shape explicit but does not make the recommendation correct. Callers must not treat a model suggestion as an approved policy decision.
- The configured default model identifier is inherited from the existing example and may need updating if the provider retires or changes model availability.

## 7. Cleanup and Azure resource state

No Azure resource was created, modified, or queried for this local lab. No cloud cleanup is required. The optional Gemini API is independently opt-in and was not called as part of the local tests.

## 8. Interview takeaways

- A deterministic rule path is easy to test and explain; a model fallback adds flexibility with variability and an external trust boundary.
- Typed results preserve provenance so a caller can distinguish a rule-backed answer, an LLM suggestion, and no match.
- Dependency injection lets the fallback behavior be validated offline and without exposing credentials.
- Keep generative recommendations out of authorization paths unless they are validated and governed by an appropriate control system.
