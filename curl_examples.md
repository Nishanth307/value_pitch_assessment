# VeriGate API — curl Examples

Refer to the examples below for interacting with VeriGate's endpoints.

Ensure the Flask app is running locally on port 5000 (`flask run`). 

Retrieve client API keys by running:
- **Local (bare-metal)**: `PYTHONPATH=. venv/bin/python3 scripts/seed.py`
- **Docker Compose**: `docker logs verigate-app`

---

## 1. Verification API (`POST /api/v1/verify`)

### A. Success Verification (VP2000 / VP2001)
```bash
curl -X POST http://127.0.0.1:5000/api/v1/verify \
  -H "X-API-Key: <YOUR_CLIENT_API_KEY>" \
  -H "X-User-Id: ab_ops_01" \
  -H "X-Forwarded-For: 127.0.0.1" \
  -H "Content-Type: application/json" \
  -d '{
    "client_ref_id": "ref_101",
    "id_type": "PAN",
    "id_number": "ABCDE1234F",
    "name": "Jane Doe"
  }'
```
**Success Response:**
```json
{
  "request_id": "req_a1b2c3d4",
  "status": "SUCCESS",
  "error_code": "VP2000",
  "data": {
    "verified": true,
    "name_match_score": 90,
    "source": "PRIMARY"
  },
  "latency_ms": 250
}
```

### B. Missing or Invalid API Key (VP4001)
```bash
curl -X POST http://127.0.0.1:5000/api/v1/verify \
  -H "X-API-Key: invalid_key" \
  -H "X-User-Id: ab_ops_01" \
  -H "Content-Type: application/json" \
  -d '{
    "client_ref_id": "ref_101",
    "id_type": "PAN",
    "id_number": "ABCDE1234F",
    "name": "Jane Doe"
  }'
```
**Response (401 Unauthorized):**
```json
{
  "request_id": "req_8a7b6c5d",
  "status": "FAILED",
  "error_code": "VP4001",
  "message": "Invalid or inactive API key"
}
```

### C. Source IP Not Whitelisted (VP4003)
```bash
curl -X POST http://127.0.0.1:5000/api/v1/verify \
  -H "X-API-Key: <YOUR_CLIENT_API_KEY>" \
  -H "X-User-Id: ab_ops_01" \
  -H "X-Forwarded-For: 8.8.8.8" \
  -H "Content-Type: application/json" \
  -d '{
    "client_ref_id": "ref_101",
    "id_type": "PAN",
    "id_number": "ABCDE1234F",
    "name": "Jane Doe"
  }'
```
**Response (403 Forbidden):**
```json
{
  "request_id": "req_0b1c2d3e",
  "status": "FAILED",
  "error_code": "VP4003",
  "message": "Client IP '8.8.8.8' is not whitelisted"
}
```

### D. Payload Validation Failure (VP4022)
```bash
curl -X POST http://127.0.0.1:5000/api/v1/verify \
  -H "X-API-Key: <YOUR_CLIENT_API_KEY>" \
  -H "X-User-Id: ab_ops_01" \
  -H "X-Forwarded-For: 127.0.0.1" \
  -H "Content-Type: application/json" \
  -d '{
    "client_ref_id": "ref_101",
    "id_type": "SSN",
    "id_number": "",
    "name": "Jane Doe"
  }'
```
**Response (422 Unprocessable Entity):**
```json
{
  "request_id": "req_f4e3d2c1",
  "status": "FAILED",
  "error_code": "VP4022",
  "message": "Field 'id_type' must be one of: PAN, DL, VOTER"
}
```

---

## 2. MIS Analytics APIs (Requires `X-Admin-Key`)

All MIS routes require the `X-Admin-Key` header (default value configured as `admin_secret_key_123`).

### A. GET Usage Report (`GET /api/v1/mis/usage`)
```bash
curl -X GET "http://127.0.0.1:5000/api/v1/mis/usage?from=2026-07-15T00:00:00Z&to=2026-07-15T23:59:59Z&group_by=client" \
  -H "X-Admin-Key: admin_secret_key_123"
```
**Response:**
```json
{
  "status": "SUCCESS",
  "data": [
    {
      "client_id": "alphabank",
      "total": 240,
      "success": 210,
      "success_via_fallback": 30,
      "not_verified": 15,
      "failed": 15,
      "avg_latency_ms": 284.15
    }
  ]
}
```

*To export this as a CSV, append `&format=csv`:*
```bash
curl -X GET "http://127.0.0.1:5000/api/v1/mis/usage?from=2026-07-15T00:00:00Z&to=2026-07-15T23:59:59Z&group_by=client&format=csv" \
  -H "X-Admin-Key: admin_secret_key_123"
```

### B. GET Errors Report (`GET /api/v1/mis/errors`)
```bash
curl -X GET "http://127.0.0.1:5000/api/v1/mis/errors?from=2026-07-15T00:00:00Z&to=2026-07-15T23:59:59Z" \
  -H "X-Admin-Key: admin_secret_key_123"
```

### C. GET Peak & Average TPS (`GET /api/v1/mis/tps`)
```bash
curl -X GET "http://127.0.0.1:5000/api/v1/mis/tps?client_id=alphabank&date=2026-07-15" \
  -H "X-Admin-Key: admin_secret_key_123"
```

### D. GET Fallback Ratios (`GET /api/v1/mis/fallback`)
```bash
curl -X GET "http://127.0.0.1:5000/api/v1/mis/fallback?from=2026-07-15T00:00:00Z&to=2026-07-15T23:59:59Z" \
  -H "X-Admin-Key: admin_secret_key_123"
```

### E. GET Client IP Activity (`GET /api/v1/mis/ips`)
```bash
curl -X GET "http://127.0.0.1:5000/api/v1/mis/ips?client_id=alphabank&from=2026-07-15T00:00:00Z&to=2026-07-15T23:59:59Z" \
  -H "X-Admin-Key: admin_secret_key_123"
```
