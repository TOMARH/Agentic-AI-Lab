# Architecture

## Current baseline

This repository begins as a local Python learning project. `01_tool_calling/hello_gemini.py` reads `GEMINI_API_KEY` from the local environment via `python-dotenv` and sends input to the Gemini Interactions API. `first_agent.py` is currently a deterministic local lookup example; despite the folder name, it does not yet implement model-directed tool calling.

Azure services and production architecture will be introduced incrementally, with identity, network boundaries, cost controls, observability, and lifecycle decisions recorded as they are designed.
