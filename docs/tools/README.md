# Tools & Technology

Maintain a record for each tool or technology encountered or installed during the sprint. Capture its purpose, version and installation method when known, configuration/authentication, permissions and trust boundaries, commands/workflows used, issues and resolutions, security considerations, and relevance to enterprise architecture. Do not record secrets or sensitive tokens.

## Current inventory

| Tool or technology | Observed state | Notes |
|---|---|---|
| Python | Project runtime | Pinned dependencies are in `requirements.txt`; exact interpreter version has not been recorded. |
| Gemini API / `google-genai` | Used by `hello_gemini.py` | Reads `GEMINI_API_KEY` from `.env` through `python-dotenv`. |
| Git for Windows | Available; version 2.53.0.windows.2 observed | Used for local version control. |
| GitHub CLI (`gh`) | Not found on PATH at repository setup | Install and record its version and authentication method when available. |
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

| Chocolatey | Available; attempted for GitHub CLI installation | Not elevated in this session; the confirmation prompt timed out, so `gh` was not installed. Retry from a normal authorized install path and record the verified version. |
