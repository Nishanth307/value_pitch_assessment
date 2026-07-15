# VeriGate Context

VeriGate is a high-throughput verification API gateway built for background verification companies and fintech clients. It validates credentials and user information by orchestrating downstream simulated identity vendors, enforcing client IP whitelisting, checking request rate limits (TPS), and generating MIS analytics reports.

## Tech Stack & Constraints
- **Framework**: Flask (Python 3.11+)
- **Database**: MongoDB (via PyMongo directly, no ODM or ORM)
- **PII Storage**: Absolutely no raw PII (names, ID numbers) allowed in database logs or files. All PII must be masked and/or SHA-256 hashed before persistence.
- **Rate Limiting**: In-memory rate limiting (sliding-window). Production systems would use a shared store like Redis.

## Clean Architecture Folder Conventions
- `app/`: Main application package
  - `config.py`: Environment-driven configuration loader
  - `extensions.py`: Singletons (e.g. PyMongo client extension)
  - `domain/`: Entities, Value Objects, and Domain Ports (abstract repository interfaces, vendor interfaces, rate limiter interfaces)
  - `application/`: Use Cases (Verify, MIS, CSV Export) and DTOs
  - `infrastructure/`: Repositories implementations (PyMongo), External adapters (vendors, in-memory rate limiter), Logging adapters
  - `interfaces/`: API endpoints, routes, request serializers/controllers
  - `services/`: Dependency Injection Container and high-level application orchestrators
  - `utils/`: Shared utilities (hashing, error codes, validator helpers)
- `scripts/`: Operational scripts (`seed.py`, `load_test.py`)
- `tests/`: Project tests directory
- `docs/`: Technical documents and architectural assumptions
- `run.py`: Root Flask entrypoint

## Running Locally
1. **Prepare Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure Environment Variables**:
   Create a `.env` file based on `.env.example`.
3. **Database Setup**:
   Ensure MongoDB is running locally (`mongod`), then seed it:
   ```bash
   PYTHONPATH=. venv/bin/python3 scripts/seed.py
   ```
4. **Start Application**:
   ```bash
   PYTHONPATH=. venv/bin/python3 run.py
   ```

## Running Tests
Run tests with:
```bash
PYTHONPATH=. venv/bin/pytest -v
```

## Coding Rules
- **Response Envelope**:
  - Success: `{ "request_id": "req_...", "status": "SUCCESS", "error_code": "VP2000", "data": { ... }, "latency_ms": 120 }`
  - Failure: `{ "request_id": "req_...", "status": "FAILED", "error_code": "VP4001", "message": "..." }`
- **Logging PII**: Never log or store raw `id_number` or raw `name`. Only store/log masked (`mask_id_number`, `mask_name`) or SHA-256 hashed versions (`hash_value`).
- **Aggregation Pipelines**: All MIS/analytics endpoints must use MongoDB aggregation pipelines. Full-collection database scans followed by Python looping/filtering are strictly forbidden.

## Error Codes Table

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| VP2000     | 200         | Verified via primary vendor |
| VP2001     | 200         | Verified via fallback vendor |
| VP2002     | 200         | Processed, but record not verified (not found / name mismatch) |
| VP4001     | 401         | Missing or invalid API key |
| VP4003     | 403         | Source IP not whitelisted |
| VP4022     | 422         | Request payload validation failed |
| VP4029     | 429         | Client TPS limit exceeded |
| VP5001     | 502         | Primary vendor failed AND fallback failed |
| VP5000     | 500         | Unhandled internal error |
