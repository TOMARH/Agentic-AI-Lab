# Tools & Technology

Maintain a record for each tool or technology encountered or installed during the sprint. Capture its purpose, version and installation method when known, configuration/authentication, permissions and trust boundaries, commands/workflows used, issues and resolutions, security considerations, and relevance to enterprise architecture. Do not record secrets or sensitive tokens.

## Current inventory

| Tool or technology | Observed state | Notes |
|---|---|---|
| Python | 3.14.4 used for Day 4 local quality checks | Runtime dependencies are pinned in `day2-function/requirements.txt`; local checks used the ignored project `.venv`. |
| Gemini API / `google-genai` | Used by `hello_gemini.py` | Reads `GEMINI_API_KEY` from `.env` through `python-dotenv`. |
| Git for Windows | Available; version 2.53.0.windows.2 observed | Used for local version control. |
| GitHub CLI (gh) | 2.101.0; authentication failed on the Day 5 run (2026-10-02) | gh auth status reported the cached TOMARH token invalid. No credential values were read or changed. PR creation and required CI review need GitHub authentication restored. |
| Azure CLI (`az`) | 2.88.0; authenticated on 2026-10-02 | Used subscription e5939949-6509-48de-964b-5f1b65c34714 for resource inventory, provider registration, what-if/deployment, settings, and REST operations. Bicep CLI 0.47.16 is available through `az bicep`. The Azure profile required an elevated command context; no token is recorded. |
| Chocolatey | Available | A GitHub CLI installation attempt was made, but its confirmation prompt timed out; that attempt did not install `gh`. The source of the currently available `gh` installation is unknown. |
| Codex CLI | 0.157.1, as recorded during the learning session | Windows setup, non-elevated launch, workspace trust, hook review, permissions, and troubleshooting are covered below. |

## Codex CLI (Windows)

### Session record

- Version observed: 0.157.1.
- Installation: standalone Windows installation succeeded and updated PATH for future PowerShell sessions.
- Authentication: ChatGPT sign-in was used during setup; do not record credentials or tokens.
- Runtime: launching from an elevated PowerShell produced a daemon startup error; using a normal, non-elevated PowerShell was the resolution.
- Workspace: launch from the intended project directory (or explicitly select it) and verify the displayed directory before trusting it. A mistaken `C:\Windows\System32` working directory was caught before trust was granted.
- Trust and permissions: workspace trust is distinct from sandbox and approval settings. Keep access scoped to the intended project and review requested actions.
- Hooks: two Azure Skills plugin hooks (`PostToolUse` telemetry and `SessionStart`) were reviewed in the session. Plugin trust, hook trust, and permission to execute tools are separate decisions; inspect hook source and command before enabling. The user chose not to enable hooks for the initial exercise.

### Practical workflow

1. Open a normal PowerShell, not an Administrator session.
2. Change to the project directory and verify the working directory.
3. Check `codex --version` and launch Codex there.
4. Verify workspace identity and review trust, permissions, and hook prompts before proceeding.
5. Ask for inspection before edits when learning an unfamiliar repository; review proposed file changes and commands.

### Enterprise relevance

CLI agents combine model reasoning with file and command tools. Workspace scope, sandbox boundaries, approval controls, and lifecycle hooks are separate security controls. Document the configured values and approval decisions that affect each team workflow.

## Day 4 additions

| Tool or technology | Observed state | Notes |
|---|---|---|
| Azure Service Bus Standard | Provisioned 2026-10-02 | Namespace sb-ai-int-likwmn7js4ffw and queue integration-events in Central India; local auth disabled, TLS 1.2 minimum, existing UAMIs, queue-scoped Sender/Receiver. Standard has a subscription-level base charge. |
| Bicep / ARM deployment | Day 4 infrastructure | Declares namespace, queue and two queue-scoped role assignments; identities are existing. |
| Azure Functions Service Bus binding | Day 4 consumer | Python v2 queue trigger; existing extension bundle range 4.x; identity-based connection settings; no connection string or Service Bus SDK package. Remote Linux package build used Flex deployment storage. |
| Azure Logic Apps HTTP + Service Bus REST | Day 4 producer | Reuses HTTP action with Logic App UAMI and Service Bus audience; no extra API connection. |
| PowerShell workflow helper | Day 4 deployment | Patches one Logic App action idempotently and preserves the rest of the definition; callback URL is never printed. |

## Day 5 additions

| Tool or technology | Observed state | Notes |
|---|---|---|
| Azure Event Grid Basic / Storage system topic | Provisioned 2026-10-02 | System-assigned identity; filters BlobCreated events to the existing incoming container; sends to existing Service Bus queue integration-events. |
| Azure Event Grid delivery metrics | Queried 2026-10-02 | Azure Monitor reported one matched and one successfully delivered event, with no delivery-failure or dead-letter series during the test interval. |
| Bicep / ARM | Day 5 template | infra/day5-eventgrid.bicep reuses Storage and Service Bus resources, creates the system topic and event subscription, and grants queue-scoped Service Bus Data Sender. |
| Azure CLI Application Insights extension | Not installed | The optional query command prompted for interactive extension installation. It was not installed; Event Grid metrics and queue counts provided runtime evidence. |
| GitHub pull-request workflow | Blocked by current authentication | The gh token was reported invalid, so no remote push, PR, CI result, review, or merge was claimed. Local Ruff and pytest quality checks passed. The unrelated Day 2 working-tree change remains unstaged. |
