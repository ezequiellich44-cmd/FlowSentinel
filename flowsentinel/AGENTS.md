# FlowSentinel - Agent Conventions & Project Rules

This document outlines the coding standards, behavioral restrictions, and architectural guidelines that any autonomous developer or agent working on this repository must adhere to.

## Core Rules (Non-Negotiable)

1. **Zero Financial Operations**:
   - This system is strictly an observation and alerting engine.
   - **NEVER** write code that signs transactions, executes trades, interacts with private keys, or manages wallets.
   
2. **Simulation Mode & Local Run**:
   - All modules must be runnable locally without external dependencies (no paid API keys, no blockchain node connections required by default).
   - In the absence of external environment variables (such as `ANTHROPIC_API_KEY`), the system must fall back gracefully to local mocked / rule-based components.

3. **Asynchronous First & Strict Typing**:
   - All Python code must be designed using `asyncio` patterns.
   - Every function, method, and variable definition must have complete Python type hints.
   
4. **Environment Configuration**:
   - All credentials, host addresses, ports, and external settings must be loaded strictly from environment variables using `pydantic-settings`.
   - Never hardcode credentials. Ensure `.env.example` remains updated and contains no real secrets.

5. **Testing Guidelines**:
   - Every new module or functionality must be accompanied by unit tests.
   - All unit tests must be executable without external infrastructure (e.g. use `fakeredis`, standard library mocking).
   - Any test requiring real external services (like a running Redis/TimescaleDB container) must be decorated with `@pytest.mark.integration` so they can be skipped during quick local check-runs.
