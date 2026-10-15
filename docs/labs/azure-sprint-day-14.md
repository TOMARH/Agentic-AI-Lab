# Azure Sprint — Day 14: Publisher-to-policy-gate contract

## Objective

Verify locally that the schema v1 event produced by the Day 10 decision publisher is accepted and classified by the Day 11 policy gate as designed. These tests exercise the Python boundary without credentials, a Service Bus connection, or Azure resources.

## Contract coverage

`tests/test_day14_policy_gate_contract.py` builds events with `build_decision_event` and passes those publisher-produced envelopes to `evaluate_decision_event`:

- An approved rule-backed topic passes as an advisory policy check.
- An LLM-sourced recommendation remains non-actionable.
- A malformed schema version is rejected.
- An event whose advisory flag is false is rejected.

Every outcome asserts `actionable` and `authorizes_execution` remain false. Passing the local rule check is not permission to execute an operation.

## Scope and limitations

The publisher-to-policy-gate contract is a local Python integration test. It does not call `publish_decision`, authenticate, contact Service Bus, or validate broker behavior. The Day 2 Function consumer and Azure resources are unchanged. These tests do not establish end-to-end delivery or execution authorization.
