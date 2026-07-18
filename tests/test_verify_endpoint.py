import pytest
import services.vendor_service as vendors_module

def test_verify_endpoint_success_logging(client, monkeypatch):
    # Mock Vendor A to succeed and skip delay
    from services.vendor_service import VendorResult
    def mock_call_a(id_type, id_number, name):
        return VendorResult(verified=True, name_match_score=99, source="PRIMARY", latency_ms=5)
    monkeypatch.setattr(vendors_module, "call_vendor_a", mock_call_a)
    
    headers = {
        "X-API-Key": "test_api_key_123",
        "X-User-Id": "test_user_01",
        "X-Forwarded-For": "192.168.1.5"
    }
    raw_id_number = "ABCDE1234F"
    raw_name = "Jane Doe"
    payload = {
        "client_ref_id": "test_ref_100",
        "id_type": "PAN",
        "id_number": raw_id_number,
        "name": raw_name
    }
    
    # Clean logs
    client.application.db.api_logs.delete_many({})
    
    res = client.post("/api/v1/verify", headers=headers, json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "SUCCESS"
    assert data["error_code"] == "VP2000"
    
    # Assert logs contain exactly 1 document
    logs = list(client.application.db.api_logs.find({}))
    assert len(logs) == 1
    log = logs[0]
    
    # Check general fields
    assert log["client_id"] == "test_client"
    assert log["user_id"] == "test_user_01"
    assert log["ip"] == "192.168.1.5"
    assert log["id_type"] == "PAN"
    assert log["http_status"] == 200
    assert log["error_code"] == "VP2000"
    assert log["vendor_used"] == "A"
    assert log["fallback_used"] is False
    assert log["circuit_open"] is False
    assert log["latency_ms"] >= 0
    
    # Assert PII masking and hashing
    assert log["masked_id_number"] == "******234F"
    assert log["masked_name"] == "J*** D**"
    
    # Assert raw values are NOT stored
    # String representation check
    log_str = str(log)
    assert raw_id_number not in log_str
    assert raw_name not in log_str
