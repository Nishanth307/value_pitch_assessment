def test_verify_stub(client):
    res = client.post("/api/v1/verify")
    assert res.status_code == 401
    data = res.get_json()
    assert data["status"] == "FAILED"
    assert data["error_code"] == "VP4001"
    assert "request_id" in data
    assert "Missing X-API-Key" in data["message"]


def test_mis_usage_stub(client):
    res = client.get("/api/v1/mis/usage")
    assert res.status_code == 401
    data = res.get_json()
    assert data["status"] == "FAILED"
    assert data["error_code"] == "VP4001"
    assert "request_id" in data
    assert "Missing or invalid Admin" in data["message"]

def test_mis_errors_stub(client):
    res = client.get("/api/v1/mis/errors")
    assert res.status_code == 401
    data = res.get_json()
    assert data["status"] == "FAILED"
    assert data["error_code"] == "VP4001"
    assert "request_id" in data
    assert "Missing or invalid Admin" in data["message"]
