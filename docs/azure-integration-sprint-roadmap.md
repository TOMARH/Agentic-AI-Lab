# Azure 30-Day Integration Architecture Sprint — Roadmap

**Status:** Reconstructed from chat; original day-by-day schedule not yet verified
**Last reviewed:** 16 October 2026
**Repository:** TOMARH/Agentic-AI-Lab

## 1. Purpose

Maintain a durable record of the sprint sequence, actual progress, required deliverables, and unresolved planning decisions. This document supplements the individual lab records, Architecture Decision Records (ADRs), and Interview Knowledge Base.

## 2. Learning-topic hierarchy

The sprint owner supplied this hierarchy:

1. Sprint Overview
2. Azure Foundation
3. Storage
4. Managed Identity
5. Key Vault
6. VNet
7. Functions
8. Logic Apps
9. Service Bus
10. Event Grid
11. Event Hubs
12. APIM
13. Agentic AI Integration
14. Enterprise Capstone
15. Architecture Decision Records

This hierarchy establishes the learning topics, not a definitive mapping of each topic to a calendar day.

## 3. Reconstructed day-by-day schedule

The following is a reconstruction from earlier chat discussions, not a verified copy of the original plan.

| Days | Reconstructed focus | Status / qualification |
|---|---|---|
| 1–4 | Azure foundations and initial integration resources | Reported closed within documented scopes |
| 5–7 | Event Grid, identity and related integration work | Reported closed; consult lab evidence |
| 8–11 | Service Bus, Functions and integration exercises | Reported closed within documented scopes |
| 12–14 | Typed decisions, policy controls and LLM-related experiments | Reported closed within documented scopes |
| 15–17 | Reliability, idempotency, failure handling and architecture evidence | Merged to main; documented limitations remain |
| 18 | Logic App / Function managed-identity route reconciliation | Closed 16 October 2026; tests, deployed route, authenticated workflow run, consumer processing and queue/DLQ state verified |
| 19–20 | Event Grid / Event Hubs phase | Planned focus requires confirmation |
| 21–22 | Integration work | Exact deliverables unconfirmed |
| 23–25 | API Management (APIM) | Exact deliverables unconfirmed |
| 26–27 | Agentic AI integration | Exact deliverables unconfirmed |
| 28–30 | Enterprise capstone | Exact deliverables unconfirmed |

The exact day-to-topic mapping and date boundaries have not been verified against an original day-by-day plan. Do not infer completion from this schedule; use merged repository records and validation evidence.

## 4. Progress baseline — 16 October 2026

- Days 1–18 were reported closed within their documented scopes; Day 18 live evidence is in [the Day 18 lab record](labs/azure-sprint-day-18.md).
- PR #14 merged Days 15–17 into main at `6ff95fd37cef32ba394440956ae059c30de1e114`.
- Merged lab documentation, tests and runtime evidence are the source of truth for completed work.
- Distinguish local tests, configuration inspection and live Azure runtime validation.
- Inspect existing Azure resources before considering new deployments.

## 5. Required lab deliverables

### A. Hands-on Lab Record — How to Recreate

Document the objective, architecture, prerequisites, resources, naming conventions, region/SKU/configuration, Portal steps, CLI/PowerShell, code/configuration, security, identity/access, networking, testing, expected results, troubleshooting, cost, cleanup and recreation checklist.

### B. Concepts Learned — Architect's Notes

Document service purpose, appropriate and inappropriate use cases, configuration trade-offs, security, cost, integration patterns, alternatives, production considerations, Agentic AI relevance, interview questions and decisions made in the lab.

### C. Architecture Decision Records

For significant architectural choices, record context, decision, rationale, alternatives, consequences, production considerations and status. Explicitly distinguish lab-only decisions from production recommendations.

## 6. Day closure criteria

A day is closed when:

1. Agreed objectives and acceptance criteria are satisfied.
2. Required automated checks pass.
3. Required live Azure validation is performed when the objective calls for it.
4. Evidence, limitations and results are documented accurately.
5. Relevant lab notes, architect's notes, ADRs and indexes are updated.
6. Changes are reviewed, committed and merged through the agreed workflow.
7. Cost and cleanup implications are addressed.

## 7. Cost and safety constraints

- Verify promotional-credit balance and expiry separately from configured budget thresholds.
- Reuse existing resources where appropriate.
- Review expected costs before provisioning billable services.
- Do not send, replay or delete live messages without explicit approval.
- Do not modify protected artifacts during routine cleanup.

## 8. Open questions

- Recover or confirm the original day-by-day schedule.
- Confirm Day 19–20 objectives and acceptance criteria against the original day-by-day plan.
- Verify current promotional-credit balance and expiry.
- Confirm capstone scenario and final deliverables.

Until confirmed, use this document as the reconstructed planning baseline and label subsequent changes clearly.
