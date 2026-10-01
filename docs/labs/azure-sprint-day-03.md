# Azure sprint: Day 3 — Logic Apps orchestration and managed identity

**Completed:** 2 October 2026 (Asia/Kolkata)
**Status:** Runtime-tested; final active workflow restored to the successful path.

## 1. Objective and outcome

Build a stateful Logic Apps Consumption workflow that invokes the Day 2 Python Function using a dedicated Logic App user-assigned managed identity (UAMI), while the Function uses its own UAMI to access Blob Storage. Verify the successful end-to-end path, verify that an unauthenticated caller is rejected, and prove that a controlled downstream HTTP failure enters a diagnostic Scope. Restore and verify the happy path at the end.

The completed architecture has two separate identity boundaries:

```text
Logic Apps Consumption / Stateful
  └─ HTTP action authenticated as Logic App UAMI
       └─ Python Function (managed-identity authentication boundary)
            └─ Function UAMI → Blob Storage
```

**Verified result:** the Logic App’s final run succeeded; its HTTP action succeeded and `Handle Function Failure` was skipped. A separate deliberate bad-route run showed HTTP failed and the failure Scope succeeded. The Function’s own successful Blob operation is the Day 2 verified behavior documented in [Day 2](azure-sprint-day-02.md); the Day 3 run proves the orchestration reached the Function successfully, but the available run summary does not independently expose a Blob response body.

## 2. Objectives and checkpoints

- Reuse the existing Day 2 Function and Blob account; add only the Logic App and its dedicated UAMI required for orchestration.
- Keep the Logic App identity distinct from the Function identity. Each identity should have only the permissions needed at its own boundary.
- Configure the HTTP action for managed-identity authentication and confirm the Function accepts that identity.
- Check the unauthenticated path separately; an HTTP 401 demonstrates that the protection boundary is active.
- Configure failure handling for both `Failed` and `TimedOut`, then test it using a temporary invalid Function route.
- Restore and publish the known-good URI, run once more, and leave the active workflow in the successful configuration.

These checkpoints describe the session’s reasoning and completed validations; they are not a verbatim prompt transcript.

## 3. Resources and configuration

| Component | Recorded configuration |
|---|---|
| Workflow | Azure Logic Apps Consumption, Stateful; existing lab resource group and Central India context from the sprint |
| Downstream Function | Existing `day2fnsprint29` Python Function App; `BlobIdentityDemo` endpoint |
| Logic App identity | Dedicated UAMI `uami-agentic-ai-lab-logicapp` (name recorded in the referenced session); principal GUID was used in the Function allow-list correction |
| HTTP action | `GET`; managed identity authentication; audience `https://management.azure.com` as recorded in the session configuration |
| Normal URI | `https://day2fnsprint29.azurewebsites.net/api/blobidentitydemo` |
| Temporary failure URI | `https://day2fnsprint29.azurewebsites.net/api/blobidentitydemo-does-not-exist` |
| Failure handler | Scope `Handle_Function_Failure`, containing Compose action `Compose_Failure_Details` |

The Logic App UAMI principal GUID and workflow resource name are not reproduced here because the accessible record does not establish them reliably. No callback URL, workflow trigger URL, Function key, token, or secret is included. The `When an HTTP request is received` trigger’s callback URL is sensitive and is intentionally omitted.

## 4. Concepts and design reasoning

### Two independent identity hops

The Logic App UAMI authenticates the outbound HTTP call to the Function. The Function has its own UAMI and uses it for its Blob data-plane operation, as documented on Day 2. The Logic App identity should not inherit Blob permissions simply because the Function needs Blob access; keeping the identities separate makes the trust and authorization boundaries easier to reason about.

Authentication identifies the caller. The Function’s authentication configuration must recognize the Logic App UAMI principal; a role assignment using the wrong identifier does not establish that caller. Authorization is evaluated separately at each downstream resource. The Day 2 Function UAMI’s Blob roles and scope remain documented in the Day 2 record.

### Stateful orchestration and failure handling

The Consumption workflow was created as **Stateful**, appropriate for this small orchestration where run history and action outcomes are useful evidence. A Scope with `runAfter` on `Failed` and `TimedOut` makes the failure branch explicit. A normal successful HTTP action skips this Scope; a downstream failure enters it and allows a diagnostic Compose action to run. The Compose text is a fixed instruction to inspect the HTTP action’s run details; it is not a dynamically extracted exception payload.

## 5. Authentication troubleshooting and security boundary

The first protected Function call returned **403**. The session identified that the Function’s allowed-principal configuration used the wrong identifier. The correction was to allow the Logic App UAMI’s **principal/object GUID**, not its client ID. After that correction, the managed-identity HTTP call succeeded. The exact first failing request details and the GUID are not available in the retained text record, so they are not invented here.

A separate unauthenticated protection check returned **401**. This is distinct from the earlier 403: the unauthenticated caller was rejected, while the configured Logic App identity was subsequently accepted after the principal allow-list correction. Do not treat either status alone as proof of Blob access; the successful authenticated workflow run and the Function’s Day 2 Blob validation cover different parts of the end-to-end chain.

Security record:

- No shared key, Function key, client secret, or callback URL is documented.
- The Logic App identity is dedicated to the Logic App → Function boundary; the Function identity is used for Function → Blob.
- Only the principal GUID belongs in a principal allow-list. Client ID identifies the application/client registration aspect and was not the accepted principal identifier in this configuration.
- Preserve the unauthenticated 401 check as evidence that the endpoint is not simply open to anonymous callers.
- The session configuration recorded audience `https://management.azure.com`; the successful runtime proves that the configured action worked in this environment. Recheck the target audience against the actual Function authentication configuration when reproducing in another environment.

## 6. Failure Scope definition

The verified Logic Apps definition fragment was:

```json
"Handle_Function_Failure": {
  "type": "Scope",
  "actions": {
    "Compose_Failure_Details": {
      "type": "Compose",
      "inputs": "Function call failed or timed out. Check the HTTP action run details for the underlying error."
    }
  },
  "runAfter": {
    "HTTP": [
      "Failed",
      "TimedOut"
    ]
  }
}
```

The designer and saved Code view showed the Scope with one Compose action. An omitted empty `runAfter` on the Compose action is normal sequencing within the Scope. The scope’s dependency is on the HTTP action and explicitly includes both failure and timeout statuses.

## 7. Validation evidence: executed and verified

| Check | Observed evidence | What it establishes |
|---|---|---|
| Initial authenticated call | HTTP returned 403 before the allowed principal was corrected | The configured identity was not yet accepted by the Function boundary |
| Principal correction | Function allow-list corrected to the Logic App UAMI principal GUID rather than client ID | Corrected the principal identifier used at the authentication boundary |
| Unauthenticated check | Request without the Logic App managed identity returned 401 | Anonymous access was rejected by the Function protection boundary |
| Authenticated normal call | HTTP action reached a successful run after the allow-list correction | Logic App managed identity authentication to the Function succeeded |
| Controlled failure run | Trigger succeeded; HTTP action failed against the deliberately invalid route; `Handle Function Failure` succeeded | Failure `runAfter` branch executed at runtime |
| Scope child action | `Compose_Failure_Details` was present in the one-action Scope; the run-history view showed the Scope succeeded | Failure handler ran; the available screenshot summary does not show the child action expanded independently |
| Final restored run | Trigger succeeded, HTTP succeeded, failure Scope was skipped; overall run succeeded | Active workflow was restored to its healthy URI and the handler is bypassed on success |
| Function-to-Blob behavior | Day 2 authorized invocation returned HTTP 200 and `Container 'incoming' contains 0 blob(s):` | The Function UAMI could list the existing container; see the Day 2 evidence for the direct data-plane result |

The run-history screenshots in the referenced conversation show the failed HTTP action with a successful failure Scope, and a later successful HTTP action with the Scope skipped. This is runtime evidence. The screenshots do not disclose the callback URL or key, and neither is reproduced here.

## 8. Exact reproduction configuration and commands

### Workflow actions

The trigger was **When an HTTP request is received**. The workflow’s `HTTP` action used:

```text
Method: GET
Authentication: Managed identity
Identity: uami-agentic-ai-lab-logicapp
Audience: https://management.azure.com
URI (normal): https://day2fnsprint29.azurewebsites.net/api/blobidentitydemo
```

The audience and identity label above are the values recorded in the session. Since the actual Logic App principal GUID and trigger schema/callback were not preserved in accessible text, retrieve them from the target environment during a reproduction; do not copy callback URLs into documentation.

### Controlled failure and restoration

Temporarily set only the HTTP URI to:

```text
https://day2fnsprint29.azurewebsites.net/api/blobidentitydemo-does-not-exist
```

Publish/save and run the workflow. The expected and observed statuses were HTTP **Failed**, `Handle Function Failure` **Succeeded**, and `Compose_Failure_Details` inside the Scope. Then restore the URI to:

```text
https://day2fnsprint29.azurewebsites.net/api/blobidentitydemo
```

Publish/save and run again. The observed final statuses were HTTP **Succeeded**, `Handle Function Failure` **Skipped**, and overall workflow **Succeeded**. The workflow was left in this restored configuration.

The exact Azure CLI or ARM deployment commands for the Logic App and UAMI were not retained in the accessible session record. The above are verified designer settings and runtime steps, not a claimed command transcript. Reproduction-only example for inspecting the identity resource (substitute the actual resource group):

```powershell
az identity show --resource-group <resource-group> --name uami-agentic-ai-lab-logicapp --query '{id:id,clientId:clientId,principalId:principalId}' --output json
```

Use the returned `principalId`/object GUID in the Function’s supported allowed-principal configuration. Do not put a client ID in a field that expects a principal/object ID. The exact Function auth configuration command is omitted because the session record does not establish which interface or exact setting was used.

## 9. Architecture decisions

### ADR 1 — Separate identities for orchestration and data access

**Decision:** Use a dedicated Logic App UAMI for the HTTP call to the Function, and retain the Function’s own UAMI for Blob access.

**Reasoning:** The caller identity and data-access identity belong to different trust boundaries. The Logic App needs to invoke the protected Function; Blob permissions remain with the workload that performs the data operation.

**Consequence:** Authentication and authorization troubleshooting can be isolated by hop. The Function allow-list must use the Logic App UAMI principal GUID where a principal/object identifier is expected.

### ADR 2 — Stateful Consumption workflow with explicit failure Scope

**Decision:** Use a Stateful Logic Apps Consumption workflow and handle HTTP failure/timeout in a Scope configured with `runAfter` statuses `Failed` and `TimedOut`.

**Reasoning:** Stateful run history made the successful and failure paths observable. A dedicated Scope keeps the error branch explicit and was demonstrated at runtime.

**Consequence:** Failed downstream calls run the Compose diagnostic; successful calls skip the handler. The Compose currently gives a static diagnostic hint and does not transform or persist the HTTP error payload.

### ADR 3 — Restore production-like happy path after negative testing

**Decision:** Use a deliberately nonexistent Function route only for the controlled failure test, then restore the valid route, publish, and run again.

**Reasoning:** Negative-path testing proves the handler while the final deployed configuration remains usable.

**Status:** Completed and verified in run history.

## 10. Cost considerations

The Logic App uses the Consumption model, so charges depend on trigger/action executions and applicable connector or data-retention meters. Stateful run history and retained data may contribute to storage-related charges according to current service terms. No precise Day 3 cost or usage total was captured. The workflow was exercised for a small number of manual runs; do not infer a monthly cost from that sample. Review the Azure Cost Management view and current Logic Apps pricing for the target subscription and region before extending the workflow. The existing Function, Storage, and monitoring costs remain covered by the Day 2 record.

## 11. Cleanup and rollback

No cleanup was performed after validation; the final workflow was intentionally left active with the valid Function URI. The temporary invalid URI was restored and is not the active configuration.

If rolling back the lab, first disable/delete the Logic App only if it is no longer needed. Remove the Logic App UAMI’s Function allow-list entry and any role assignments granted specifically for this integration, then delete the dedicated UAMI only after confirming no other workload uses it. Do not remove the Day 2 Function UAMI’s Blob roles or delete the shared Function, storage account, or existing containers as part of Day 3 rollback. Exact delete commands are omitted because the resource names, scopes, and assignment IDs are not reliably present in the retained Day 3 record.

## 12. Reproduction checklist

1. Confirm the existing Day 2 Function is healthy and its authorized Blob operation still works; use [Day 2](azure-sprint-day-02.md) for the verified baseline.
2. Create or identify a Logic Apps Consumption workflow with the **Stateful** workflow type.
3. Attach a dedicated Logic App UAMI and record its client ID and principal/object GUID privately for configuration; do not store secrets or callback URLs in the repository.
4. Configure the Function’s supported authentication/allow-list boundary for the Logic App UAMI using the principal/object GUID, not the client ID.
5. Verify that a request without managed-identity authentication receives HTTP 401.
6. Add the `When an HTTP request is received` trigger and a `GET` HTTP action to the valid Function URI using managed-identity authentication; configure the intended audience for the target Function’s authentication setup.
7. Add `Handle_Function_Failure` as a Scope after `HTTP`, with `runAfter` set to `Failed` and `TimedOut`; add `Compose_Failure_Details` inside it.
8. Publish and run the valid workflow. Confirm the trigger and HTTP succeed and the failure Scope is skipped.
9. Temporarily use the documented invalid route, publish, and run. Confirm HTTP fails and the failure Scope/Compose run.
10. Restore the valid Function URI, publish, and run a final time. Confirm HTTP succeeds, the Scope is skipped, and the overall workflow succeeds.
11. Review run history, Function authentication settings, UAMI principal, RBAC boundaries, and current costs. Keep callback URLs, keys, and tokens out of notes and screenshots shared externally.

For a reproduction in another environment, validate the HTTP audience against that Function’s actual authentication configuration; the recorded `https://management.azure.com` value is a session-specific observed setting.

## 13. Tools & Technology documentation

| Tool or technology | Use in Day 3 | Evidence / caveat |
|---|---|---|
| Azure Logic Apps Consumption | Stateful orchestration, HTTP action, run history | Designer configuration and runtime screenshots were reviewed; exact workflow ARM export was not retained |
| User-assigned managed identity | Dedicated Logic App caller identity | Principal GUID, rather than client ID, corrected the Function allow-list |
| Azure Functions (Python v2) | Protected downstream HTTP endpoint; its own UAMI reaches Blob | Existing Day 2 deployment and authentication details are in the Day 2 record |
| Azure Blob Storage | Function’s data-plane target | Day 2 invocation returned a successful container listing |
| Azure Portal / Logic Apps designer | Configure, publish, and inspect runs | Visible workflow labels and run statuses are the available Day 3 runtime evidence |

This adds Azure Logic Apps, Logic Apps managed-identity HTTP authentication, Stateful workflow run history, and Scope/`runAfter` error handling to the project’s Tools & Technology inventory. The repository-wide inventory update is outside this Day 3 lab-file-only change; this section records the technologies encountered in this lab.

## 14. Interview takeaways

- Explain the end-to-end trust chain as two identity hops: Logic App UAMI to Function, then Function UAMI to Blob.
- A managed identity client ID and principal/object ID are different identifiers; use the one expected by the configuration field. The 403 here was corrected by allowing the UAMI principal GUID.
- An unauthenticated HTTP 401 is useful negative evidence for a protected endpoint, but it does not prove the authenticated identity has the intended permissions.
- A successful downstream Function call and a successful Function-to-Blob operation are distinct validation claims; test and document each boundary.
- `runAfter` can route failed or timed-out work into an explicit Scope. Verify behavior in run history instead of relying only on a saved definition.
- Test error handling with a controlled invalid dependency, then restore the valid configuration and record a final happy-path run.
- A static Compose diagnostic tells an operator where to inspect; a production handler may additionally need structured error capture, alerting, retries, idempotency, or compensation, depending on requirements.

## 15. Next-lab dependency

Day 3 builds on the deployed Function and UAMI-based Blob access from [Day 2](azure-sprint-day-02.md). The Logic App is left active on the valid Function URI with both positive and negative runtime evidence recorded. The next sprint lab can build on this protected orchestration pattern; no specific next-day design is asserted here because it was not established in the retained session record.
