import pytest
from datetime import datetime, timezone, timedelta

@pytest.fixture
def seed_mis_logs(app):
    with app.app_context():
        # Clear logs first
        app.db.api_logs.delete_many({})
        
        # Base date: 2026-07-15
        base_time = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        
        logs = [
            # Client: test_client
            # 1. Success Primary
            {
                "request_id": "req_1",
                "client_id": "test_client",
                "user_id": "test_user_01",
                "ip": "192.168.1.5",
                "endpoint": "/api/v1/verify",
                "id_type": "PAN",
                "http_status": 200,
                "error_code": "VP2000",
                "vendor_used": "A",
                "fallback_used": False,
                "circuit_open": False,
                "latency_ms": 100,
                "created_at": base_time
            },
            # 2. Success Fallback
            {
                "request_id": "req_2",
                "client_id": "test_client",
                "user_id": "test_user_01",
                "ip": "192.168.1.5",
                "endpoint": "/api/v1/verify",
                "id_type": "PAN",
                "http_status": 200,
                "error_code": "VP2001",
                "vendor_used": "B",
                "fallback_used": True,
                "circuit_open": False,
                "latency_ms": 200,
                "created_at": base_time + timedelta(seconds=1)
            },
            # 3. Processed Not Verified
            {
                "request_id": "req_3",
                "client_id": "test_client",
                "user_id": "test_user_02",
                "ip": "192.168.1.5",
                "endpoint": "/api/v1/verify",
                "id_type": "DL",
                "http_status": 200,
                "error_code": "VP2002",
                "vendor_used": "A",
                "fallback_used": False,
                "circuit_open": False,
                "latency_ms": 150,
                "created_at": base_time + timedelta(seconds=2)
            },
            # 4. Blocked IP
            {
                "request_id": "req_4",
                "client_id": "test_client",
                "user_id": "test_user_02",
                "ip": "192.168.1.10", # Not whitelisted
                "endpoint": "/api/v1/verify",
                "id_type": None,
                "http_status": 403,
                "error_code": "VP4003",
                "vendor_used": None,
                "fallback_used": False,
                "circuit_open": False,
                "latency_ms": 5,
                "created_at": base_time + timedelta(seconds=3)
            },
            
            # TPS Burst: three requests in the exact same second for Peak TPS checking
            # (at base_time + 10 seconds)
            {
                "request_id": "req_burst1",
                "client_id": "test_client",
                "user_id": "test_user_01",
                "ip": "127.0.0.1",
                "endpoint": "/api/v1/verify",
                "id_type": "PAN",
                "http_status": 200,
                "error_code": "VP2000",
                "vendor_used": "A",
                "fallback_used": False,
                "circuit_open": False,
                "latency_ms": 120,
                "created_at": base_time + timedelta(seconds=10)
            },
            {
                "request_id": "req_burst2",
                "client_id": "test_client",
                "user_id": "test_user_01",
                "ip": "127.0.0.1",
                "endpoint": "/api/v1/verify",
                "id_type": "PAN",
                "http_status": 200,
                "error_code": "VP2000",
                "vendor_used": "A",
                "fallback_used": False,
                "circuit_open": False,
                "latency_ms": 80,
                "created_at": base_time + timedelta(seconds=10, milliseconds=200)
            },
            {
                "request_id": "req_burst3",
                "client_id": "test_client",
                "user_id": "test_user_01",
                "ip": "127.0.0.1",
                "endpoint": "/api/v1/verify",
                "id_type": "PAN",
                "http_status": 200,
                "error_code": "VP2000",
                "vendor_used": "A",
                "fallback_used": False,
                "circuit_open": False,
                "latency_ms": 100,
                "created_at": base_time + timedelta(seconds=10, milliseconds=400)
            }
        ]
        
        app.db.api_logs.insert_many(logs)
        yield
        app.db.api_logs.delete_many({})

def test_mis_usage_report(client, seed_mis_logs):
    headers = {"X-Admin-Key": "admin_secret_key_123"}
    
    # 1. JSON Report Grouped by Client
    res = client.get(
        "/api/v1/mis/usage?from=2026-07-15T00:00:00Z&to=2026-07-15T23:59:59Z&group_by=client",
        headers=headers
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "SUCCESS"
    
    records = data["data"]
    assert len(records) == 1
    rec = records[0]
    assert rec["client_id"] == "test_client"
    assert rec["total"] == 7
    # VP2000 (x4) + VP2001 (x1) = 5 Success
    assert rec["success"] == 5
    assert rec["success_via_fallback"] == 1
    assert rec["not_verified"] == 1 # VP2002
    assert rec["failed"] == 1 # VP4003
    # Latencies: 100 + 200 + 150 + 5 + 120 + 80 + 100 = 755 / 7 = 107.86
    assert abs(rec["avg_latency_ms"] - 107.86) < 0.1
    
    # 2. CSV Report Export
    res_csv = client.get(
        "/api/v1/mis/usage?from=2026-07-15T00:00:00Z&to=2026-07-15T23:59:59Z&group_by=client&format=csv",
        headers=headers
    )
    assert res_csv.status_code == 200
    assert res_csv.headers["Content-Type"] == "text/csv"
    csv_content = res_csv.data.decode("utf-8")
    assert "client_id,total,success" in csv_content
    assert "test_client,7,5,1,1,1" in csv_content

def test_mis_errors_report(client, seed_mis_logs):
    headers = {"X-Admin-Key": "admin_secret_key_123"}
    res = client.get(
        "/api/v1/mis/errors?from=2026-07-15T00:00:00Z&to=2026-07-15T23:59:59Z",
        headers=headers
    )
    assert res.status_code == 200
    records = res.get_json()["data"]
    
    # Error codes check: VP2000 (4), VP2001 (1), VP2002 (1), VP4003 (1)
    err_map = {r["error_code"]: r["count"] for r in records}
    assert err_map["VP2000"] == 4
    assert err_map["VP2001"] == 1
    assert err_map["VP2002"] == 1
    assert err_map["VP4003"] == 1

def test_mis_tps_report(client, seed_mis_logs):
    headers = {"X-Admin-Key": "admin_secret_key_123"}
    res = client.get(
        "/api/v1/mis/tps?client_id=test_client&date=2026-07-15",
        headers=headers
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    
    # Peak TPS is in the burst second (which has 3 requests in the same second)
    assert data["peak_tps"] == 3
    # Seconds with traffic: 12:00:00 (1), 12:00:01 (1), 12:00:02 (1), 12:00:03 (1), 12:00:10 (3) -> 5 seconds.
    # Total requests: 7. Avg TPS = 7 / 5 = 1.4
    assert data["avg_tps"] == 1.4
    
    # P95 latency: Sorted latencies: [5, 80, 100, 100, 120, 150, 200]
    # Size = 7. Index = floor(0.95 * 7) = floor(6.65) = 6. Element at 6 is 200.
    assert data["p95_latency_ms"] == 200

def test_mis_fallback_report(client, seed_mis_logs):
    headers = {"X-Admin-Key": "admin_secret_key_123"}
    res = client.get(
        "/api/v1/mis/fallback?from=2026-07-15T00:00:00Z&to=2026-07-15T23:59:59Z",
        headers=headers
    )
    assert res.status_code == 200
    records = res.get_json()["data"]
    assert len(records) == 1
    rec = records[0]
    assert rec["client_id"] == "test_client"
    assert rec["total_success"] == 5
    assert rec["served_by_fallback"] == 1
    # Fallback ratio: 1 / 5 = 20%
    assert rec["fallback_ratio_pct"] == 20.0

def test_mis_ips_report(client, seed_mis_logs):
    headers = {"X-Admin-Key": "admin_secret_key_123"}
    res = client.get(
        "/api/v1/mis/ips?client_id=test_client&from=2026-07-15T00:00:00Z&to=2026-07-15T23:59:59Z",
        headers=headers
    )
    assert res.status_code == 200
    records = res.get_json()["data"]
    
    # IPs checked: 192.168.1.5 (3 hits), 192.168.1.10 (1 hit), 127.0.0.1 (3 hits)
    ip_map = {r["ip"]: r for r in records}
    
    assert ip_map["192.168.1.5"]["total_hits"] == 3
    assert ip_map["192.168.1.5"]["blocked_hits"] == 0
    assert ip_map["192.168.1.5"]["whitelisted"] is True
    
    assert ip_map["192.168.1.10"]["total_hits"] == 1
    assert ip_map["192.168.1.10"]["blocked_hits"] == 1
    assert ip_map["192.168.1.10"]["whitelisted"] is False # Not whitelisted
