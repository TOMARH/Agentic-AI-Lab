# Azure sprint — Day 9: Local decision model and typed decisions

**Status:** Implemented as a local-only Python exercise. No Azure deployment or live Gemini request is claimed.

## 1. Objective and concepts

Build a small architecture decision component that makes deterministic recommendations for known topics, returns a typed result with provenance, and optionally asks Gemini for a suggestion on an unknown topic. This lab introduces:

- **Rules-first routing:** use predictable local policy for known inputs before considering a probabilistic model.
- **Typed result / provenance:** make the decision source (`rule`, `llm`, or `unmatched`) visible to callers instead of returning an ambiguous string.
- **Dependency injection:** pass the optional model function into `decide()` so its behavior can be tested with a fake, offline implementation.
- **Trust boundary:** model text is untrusted advice. A type annotation records the source; it does not validate correctness or confer authority.

The exercise is deliberately local and does not alter the Azure integration architecture. It can later be used as a decision component behind a governed integration boundary, with policy and operational controls added separately.

## 2. Architecture

```text
CLI topic
   |
   v
decide(topic)
   | normalize with strip + casefold
   | exact local rule? -- yes --> Decision(source="rule")
   |
   no
   | -- --llm explicitly enabled? -- yes --> Gemini -> Decision(source="llm")
   |                                      no
   +---------------------------------------> Decision(source="unmatched")
```

`Decision` is a frozen dataclass containing `topic`, `recommendation`, `source`, and `rationale`. Rules are checked before the injected fallback. The provider SDK import happens only inside `gemini_recommendation()`, so importing the module, running a known rule, and testing the local decision function do not require a key or network access.

## 3. Reasoning prompts and checkpoints

The implementation checkpoint asked: should the model be the default decision-maker, or only a visible opt-in fallback after deterministic rules? The chosen design preserves a deterministic path and makes provider use explicit with `--llm`. Known topics must not call the fallback, even when it is injected; tests enforce that invariant.

The provider instruction sent by the code is:

> Give one concise software architecture principle for this topic. Return a recommendation, not code. Topic: {topic}

The user-facing reasoning checkpoint selected rules-first behavior with typed source information. This keeps the example useful for learning while constraining external calls. The recommendation remains a suggestion; no hidden policy or authorization decision is delegated to Gemini.

## 4. Design decisions and alternatives

1. **Rules first.** Exact normalized topic keys are deterministic and do not invoke Gemini. Always asking an LLM would add latency, provider dependency, cost, and variation even for known topics.
2. **Typed decisions.** The dataclass exposes provenance (`rule`, `llm`, or `unmatched`) and rationale alongside the recommendation. Plain strings conceal how the result was produced.
3. **Explicit optional provider.** Gemini is used only when the caller supplies the fallback, which the CLI does only with `--llm`, and only after a rule miss. Otherwise the result is an explicit `unmatched` value.
4. **Advice, not authority.** LLM output is not schema-checked, policy-validated, filtered, or reviewed. It must not control authorization, safety, routing, or production policy without a separately designed validation and governance layer.
5. **Injected dependency.** Tests pass a fake callable instead of making live requests. This makes the decision contract fast, repeatable, and credential-free to verify.

## 5. Configuration, reproduction, and trust boundary

Run commands from the repository root in the project virtual environment. The rule-only path needs no external credentials.

| Setting | Required | Purpose |
|---|---:|---|
| `GEMINI_API_KEY` | Only for an unmatched topic with `--llm` | Authenticates the optional Gemini API request. Never place its value in source, shell history, logs, or lab notes. |
| `GEMINI_MODEL` | No | Optional model override; code default is `gemini-3.6-flash`. |

To exercise the optional provider path in PowerShell, set the key in the current process environment without echoing or committing it, then run:

```powershell
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new("", (Read-Host -AsSecureString "Gemini API key")).Password
python 01_tool_calling/first_agent.py "event sourcing" --llm
Remove-Item Env:GEMINI_API_KEY
```

The prompt sends the normalized topic and fixed instruction to the configured model provider. Treat the returned text as untrusted external content. Only opt in when the provider account, data handling, and usage costs are acceptable. The key is not loaded from `.env` in this module; environment configuration as shown above is required for this CLI path.

## 6. Validation evidence

The PR implementation record reports five local tests passing, successful rule and unmatched CLI examples, successful `compileall`, and a clean `git diff --check`. These checks are local; they do not establish live Gemini or Azure behavior. The focused commands are:

```powershell
python -m pytest tests/test_decision_model.py -v
python 01_tool_calling/first_agent.py messaging
python 01_tool_calling/first_agent.py "event sourcing"
python -m compileall 01_tool_calling/first_agent.py tests/test_decision_model.py
git diff --check
```

Expected behavior: `messaging` reports source `rule`; `event sourcing` without `--llm` reports source `unmatched`. Tests cover known-rule precedence, unmatched provenance, fake-fallback provenance and invocation, empty-topic rejection, and empty model-answer rejection. The fake fallback proves the integration contract without a live provider request.

The PR's GitHub quality check also passed. No live Gemini call and no Azure command/resource operation was part of the reported validation. When reproducing, retain the actual command output and test summary in the PR or session record rather than inferring output from these expected behaviors.

## 7. Tools and technologies used

- Python and the standard library (`dataclasses`, `typing`, `argparse`, `os`) implement the local model and CLI.
- `pytest` exercises the decision contract with an injected fake callable.
- Google Gen AI Python SDK (`google-genai`) is imported lazily for the optional Gemini Interactions API path. The model default is in code; no live call was needed for local checks. See the project [Tools & Technology inventory](../tools/README.md) for setup and trust-boundary notes.
- Git and GitHub Actions provide branch review and the repository quality check; the PR summary reports its required check passed.
- Azure CLI and Azure resources are not used by this lab.

## 8. Security, cost, and operations

- **Secrets:** do not commit `.env`, API keys, or provider responses containing sensitive information. Use a process-scoped environment variable for the manual opt-in example and clear it after use.
- **Data boundary:** the topic leaves the local process only when `--llm` is enabled for an unmatched topic. Do not send confidential or regulated topic text unless permitted by the provider's current terms and organizational policy.
- **Model risk:** the sample has no retry/timeout strategy, structured output contract, content filtering, or recommendation validation. Provider errors may stop the CLI.
- **Azure cost:** no Azure resource was created or changed, so this lab adds no Azure resource cost and requires no Azure cleanup.
- **Provider cost:** rule-only runs and tests use no Gemini API. A manually enabled live request may incur provider charges according to the account's current pricing and usage; this lab does not estimate or verify that spend.

## 9. Cleanup and Azure resource state

No Azure resource was created, modified, or queried for this lab; no cloud cleanup is required. Local cleanup is to clear the process environment variable after a manual provider run and remove any locally retained sensitive output according to the user's normal handling rules. No live Gemini request is represented as executed by the PR validation record.

## 10. Next-lab dependency

Day 9 supplies a local decision contract and provenance field that a later integration lab can carry as message metadata or an explicit application result. The next lab should preserve the distinction between rule-backed, model-suggested, and unmatched decisions, and must add its own authorization, validation, observability, and cost controls before any model suggestion affects an Azure workflow. No Azure provisioning is a prerequisite for reproducing this lab.

## 11. Interview takeaways

- A deterministic rule path is straightforward to test and explain; a model fallback adds flexibility with variability and a provider trust boundary.
- Typed results preserve provenance, helping downstream systems distinguish policy-backed outcomes from model suggestions or missing rules.
- Dependency injection validates the fallback contract offline without credentials, network traffic, or provider cost.
- Generative output should not become an authorization or safety decision unless a separate, auditable validation and governance design makes that use appropriate.
