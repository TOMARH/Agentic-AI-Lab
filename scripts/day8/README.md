# Day 8: Service Bus DLQ Inspection & Controlled Replay Tooling

Operational framework for inspecting, remediating, and replaying dead-lettered messages in Azure Service Bus queues within an asynchronous Azure Functions architecture.

---

## 1. Architecture

+-----------------------------------------------------------------------------------------+
|                                    Azure Service Bus                                    |
|                                                                                         |
|   +--------------------+     Delivery Attempts >= 5       +-------------------------+   |
|   | integration-events | -------------------------------> |    $DeadLetterQueue     |   |
|   +--------------------+                                  +-------------------------+   |
|             ^                                                          |                |
|             |                scripts/day8/dlq_manager.py               |                |
|             +----------------------------------------------------------+                |
|                               (Replay + Trace Preservation)                             |
+-----------------------------------------------------------------------------------------+
|
v
+-----------------------+
|  Azure Functions      |
|  day2fnsprint29       |
|  (Flex Consumption)   |
|                       |
|  Identity: UAMI       |
|  RBAC: Data Receiver  |
+-----------------------+

### Security & Infrastructure Constraints
- **Local Auth Disabled:** SAS connection strings are strictly prohibited. All authentication relies on Azure AD (Entra ID) Managed Identities and `DefaultAzureCredential`.
- **RBAC Roles Required:**
  - **Azure Service Bus Data Receiver:** Required for reading and peeking active queues and `$DeadLetterQueue`.
  - **Azure Service Bus Data Sender:** Required for replaying messages back to the active queue.
- **W3C Distributed Tracing:** Telemetry headers (`traceparent`) are extracted, validated, and preserved across replay loops to maintain end-to-end lineage across Application Insights and Log Analytics.

---

## 2. CLI Tooling Usage

### Non-Destructive DLQ Inspection (`peek`)
Peeks up to a specified count of messages from the DLQ without locking or modifying queue state:

```powershell
python scripts/day8/dlq_manager.py peek --count 5