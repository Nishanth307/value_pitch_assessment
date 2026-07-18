# VeriGate Context

VeriGate is a simplified Flask + MongoDB API gateway for identity verification. It validates client credentials, checks rate limits, orchestrates simulated verification vendors (with fallback and circuit breaker logic), and logs processed results to MongoDB (with PII masking). It also provides an admin-protected MIS reporting dashboard.

## Folder Structure

```
verigate/
├── app.py              # Application factory and app setup
├── config.py           # Configuration loader
├── models.py           # Database connection & seed layout
├── routes/
│   ├── __init__.py     # Blueprint registration setup
│   ├── verify.py       # POST /api/v1/verify
│   └── mis.py          # GET /api/v1/mis/* (admin protected reports)
├── services/
│   ├── vendor_service.py  # Simulated Vendor A and Vendor B logic
│   ├── rate_limiter.py    # Sliding window/in-memory rate limiting
│   └── log_service.py     # Database logging with PII masking/hashing
├── utils/
│   ├── security.py     # Hashing and masking functions
│   └── helpers.py      # Date parsing and formatting
├── scripts/
│   ├── seed.py         # Seeds client database with 3 clients
│   └── load_test.py    # Simulates concurrent traffic for testing
├── tests/              # Test suite
└── CLAUDE.md           # Developer guide & commands
```

## Running Locally

1. **Setup Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run MongoDB**:
   Ensure MongoDB is running locally.

3. **Seed Database**:
   ```bash
   python3 scripts/seed.py
   ```

4. **Start Application**:
   ```bash
   python3 app.py
   ```

## Running Tests

Run the test suite with:
```bash
pytest
```

## Coding Style & Principles
- **Clarity & Simplicity**: Simple functions, straightforward logic, minimal abstractions.
- **Explicit Comments**: Document *what* is done and *why* (especially for fallbacks, rate limiting, and aggregations).
- **Security First**: Absolutely no raw PII in database. Use masking and hashing helpers.
