# ADR 0004: Standard Service Bus queue between Logic Apps and Functions

- **Status:** Accepted
- **Date:** 2 October 2026
- **Context:** Day 4 connects an existing Consumption Logic App to a Flex Consumption Python Function using existing UAMIs in a shared lab resource group. No namespace existed; the Service Bus provider was unregistered. The user selected Standard queue after comparing Basic queue and Standard topic.
- **Decision:** Create one Standard namespace and one queue. Disable local/SAS auth. Grant the Logic App UAMI queue-scoped Data Sender and the Function UAMI queue-scoped Data Receiver. Use the existing HTTP action with the Logic App UAMI to call the Service Bus REST endpoint; use a Functions queue trigger with identity-based connection settings.
- **Alternatives:** Basic is lower cost but does not meet the selected managed-identity integration path. A topic adds fan-out without another consumer. A separate API connection is unnecessary because the existing HTTP action supports managed identity and Service Bus accepts Entra tokens.
- **Consequences:** Producer and consumer are decoupled; access is split by role and queue scope; no Service Bus secret is stored. Standard has a subscription-level base charge plus usage while provisioned. Data Receiver does not grant the extra namespace read permission for more accurate Function scaling, so this lab accepts peek-based estimates instead of Data Owner.
- **Security:** TLS 1.2 minimum, local auth disabled, public endpoint for current hosted apps, queue-scoped RBAC, payload omitted from logs.
- **Revisit when:** A second consumer needs fan-out, private networking is introduced, or Standard's base charge is no longer justified.
