import pytest
from app.extensions import mongo
from app.services import vendors as vendors_module
from app.services.vendors import VendorResult
from app.services import rate_limiter as tps_limiter

@pytest.fixture(autouse=True)
def mock_vendors_instant(monkeypatch):
    """Mock both vendors to return instantly with 0 latency for middleware tests."""
    def mock_call_a(id_type, id_number, name):
        return VendorResult(verified=True, name_match_score=100, source="PRIMARY", latency_ms=0)
    def mock_call_b(id_type, id_number, name):
        return VendorResult(verified=True, name_match_score=100, source="FALLBACK", latency_ms=0)
    
    monkeypatch.setattr(vendors_module, "call_vendor_a", mock_call_a)
    monkeypatch.setattr(vendors_module, "call_vendor_b", mock_call_b)

def test_auth_missing_api_key(client):
    res = client.post("/api/v1/verify", json={})
    assert res.status_code == 401
    data = res.get_json()
    assert data["status"] == "FAILED"
    assert data["error_code"] == "VP4001"
    assert "Missing X-API-Key" in data["message"]

def test_auth_invalid_api_key(client):
    res = client.post("/api/v1/verify", headers={"X-API-Key": "invalid_key"})
    assert res.status_code == 401
    data = res.get_json()
    assert data["error_code"] == "VP4001"
    assert "Invalid or inactive" in data["message"]

def test_auth_missing_user_id(client):
    res = client.post(
        "/api/v1/verify",
        headers={"X-API-Key": "test_api_key_123"},
        json={}
    )
    assert res.status_code == 422
    data = res.get_json()
    assert data["error_code"] == "VP4022"
    assert "X-User-Id" in data["message"]

def test_ip_not_whitelisted(client):
    res = client.post(
        "/api/v1/verify",
        headers={
            "X-API-Key": "test_api_key_123",
            "X-User-Id": "test_user_01",
            "X-Forwarded-For": "192.168.1.10"
        },
        json={}
    )
    assert res.status_code == 403
    data = res.get_json()
    assert data["error_code"] == "VP4003"
    assert "IP" in data["message"]

def test_payload_validation(client):
    headers = {
        "X-API-Key": "test_api_key_123",
        "X-User-Id": "test_user_01",
        "X-Forwarded-For": "192.168.1.5"
    }
    
    # Clear rate limiter store before each check to prevent rate limiting (TPS is 2)
    tps_limiter._limiter_store.clear()
    
    # Missing client_ref_id
    res = client.post("/api/v1/verify", headers=headers, json={"id_type": "PAN", "id_number": "123", "name": "John"})
    assert res.status_code == 422
    assert "client_ref_id" in res.get_json()["message"]
    
    tps_limiter._limiter_store.clear()

    # Invalid id_type
    res = client.post("/api/v1/verify", headers=headers, json={"client_ref_id": "ref", "id_type": "SSN", "id_number": "123", "name": "John"})
    assert res.status_code == 422
    assert "id_type" in res.get_json()["message"]
    
    tps_limiter._limiter_store.clear()

    # Missing id_number
    res = client.post("/api/v1/verify", headers=headers, json={"client_ref_id": "ref", "id_type": "PAN", "id_number": "", "name": "John"})
    assert res.status_code == 422
    assert "id_number" in res.get_json()["message"]

def test_tps_limiter(client):
    headers = {
        "X-API-Key": "test_api_key_123",
        "X-User-Id": "test_user_01",
        "X-Forwarded-For": "192.168.1.5"
    }
    payload = {
        "client_ref_id": "ref_1",
        "id_type": "PAN",
        "id_number": "ABCDE1234F",
        "name": "Jane Doe"
    }
    
    tps_limiter._limiter_store.clear()
    
    # Firing 3 requests in immediate succession should trigger a rate limit error on the 3rd request (limit = 2).
    res1 = client.post("/api/v1/verify", headers=headers, json=payload)
    res2 = client.post("/api/v1/verify", headers=headers, json=payload)
    res3 = client.post("/api/v1/verify", headers=headers, json=payload)
    
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res3.status_code == 429
    
    data = res3.get_json()
    assert data["error_code"] == "VP4029"
    assert "TPS limit" in data["message"]
