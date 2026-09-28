# Agentic AI Lab

A hands-on learning repository evolving from a small Python/Gemini example toward enterprise AI and Azure integration architecture. Existing experiments are retained and documented as the lab grows.

## Current project

- `01_tool_calling/`: introductory Python examples. `first_agent.py` currently demonstrates a local architecture-principle lookup; `hello_gemini.py` calls the Gemini Interactions API.
- `requirements.txt`: pinned Python dependencies for the current examples.
- `docs/`: learning notes, architecture decisions, and tool/technology records.

## Local setup

1. Use Python 3.11 or a compatible version supported by the installed dependencies.
2. Create and activate a virtual environment.
3. Install dependencies with `python -m pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and add your own `GEMINI_API_KEY` to `.env`.
5. Run examples from the repository root, for example `python 01_tool_calling/first_agent.py`.

Never commit `.env` or paste API keys into documentation, issues, or chat. `.env.example` is a placeholder-only template.

## Learning path

The repository will grow incrementally: agent foundations, Azure platform and integration services, security and identity, observability, RAG and orchestration, and an enterprise integration capstone. New Azure resources should be planned with explicit budget limits, alerts, and cleanup steps before provisioning.

## Documentation

- [Architecture overview](docs/architecture/README.md)
- [Architecture decisions](docs/adr/README.md)
- [Labs and sprint notes](docs/labs/README.md)
- [Tools & Technology](docs/tools/README.md)
