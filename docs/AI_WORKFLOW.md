# AI Workflow Reflection

This document provides a transparent and reflective account of the development process for VeriGate, outlining the interaction between the AI coding assistant and the developer.

## Representative Prompts Used
Below are 5 representative prompts used during this session to scaffold, refine, and build VeriGate:

1. **Scaffolding and Setup (Prompt 0)**: Setup the Flask application structure, dependency files (`requirements.txt`, `.env.example`), configuration models, Mongo extension hooks, blueprints with 501 stub responses, and the baseline context file `CLAUDE.md`.
2. **Error Code Registry & Exceptions (Prompt 1)**: Implement the custom `AppError` exceptions hierarchy and create `app/utils/error_codes.py` to map error codes to HTTP statuses, write PII masking and hashing logic, and develop `scripts/seed.py`.
3. **Simulated Vendors & Fallbacks (Prompt 2)**: Create Vendor A and B simulators under `app/vendors/` alongside a thread-based join timeout orchestrator and sliding-window circuit breaker.
4. **Decorators & Request Hooks (Prompt 3 & 4)**: Wire middleware decorators for Auth, IP Whitelist, TPS rate limiting, and Payload Validation on the `POST /api/v1/verify` endpoint, and implement `after_request` request logging with PII compliance.
5. **MIS Analytics Aggregation Pipelines (Prompt 5)**: Develop MongoDB aggregation queries for usage reports, errors frequency, fallback ratios, Peak/Average TPS calculation, and whitelisted IP hits, with support for CSV formats.

## Catching and Fixing Errors
During test execution, we encountered two significant errors that were caught and resolved:

### 1. Flask Config Lookup Error (AttributeError)
* **What went wrong**: The vendor components tried to access Flask configuration settings using standard attribute lookups (`getattr(cfg, "VENDOR_TIMEOUT_BUDGET_MS")`).
* **How it was caught**: Running `test_vendor_orchestrator.py` threw `AttributeError: <Config...> has no attribute 'VENDOR_TIMEOUT_BUDGET_MS'`.
* **How it was fixed**: We updated `orchestrator.py`, `vendor_a.py`, and `vendor_b.py` to check if the configuration object supports dictionary access (`hasattr(cfg, "get")`) and use `cfg.get()` instead of `getattr()`.

### 2. Global Test State Pollution (Rate Limiter and Circuit Breaker)
* **What went wrong**: Middleware tests for payload validation failed with a `429 Too Many Requests` error because requests executed in prior tests persisted in the in-memory global deques for rate limiting and circuit breaking.
* **How it was caught**: Running the full pytest suite failed tests sequentially in `tests/test_middleware.py`.
* **How it was fixed**: We updated the `cleanup_and_reset` autouse fixture in `tests/conftest.py` to call `.clear()` on `tps_limiter._limiter_store` and reset the circuit breaker parameters (`_failure_timestamps.clear()`) before every unit test.

## Development Estimates
- **AI-Generated Code**: **97%**
- **Hand-Edited/Guided Code**: **3%** (primarily around conftest resets, safe config lookups, and SHA-256 test assertions).
