import pytest
import time
import services.vendor_service as orchestrator
from services.vendor_service import VendorTimeoutError, VendorFailureError, VendorResult
from utils.errors import VendorFailureError as AppVendorFailureError

@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset the circuit breaker module-level state before each test."""
    orchestrator._failure_timestamps.clear()
    orchestrator._circuit_open_until = 0.0

def test_orchestrator_vendor_a_success(monkeypatch):
    # Mock Vendor A to always succeed quickly
    def mock_call_a(id_type, id_number, name):
        return VendorResult(verified=True, name_match_score=95, source="PRIMARY", latency_ms=10)
    monkeypatch.setattr(orchestrator, "call_vendor_a", mock_call_a)

    result = orchestrator.verify_identity("PAN", "ABCDE1234F", "Test User")
    assert result["verified"] is True
    assert result["source"] == "PRIMARY"
    assert result["fallback_used"] is False
    assert result["circuit_open"] is False
    assert result["error_code"] == "VP2000"

def test_orchestrator_vendor_a_not_verified(monkeypatch):
    def mock_call_a(id_type, id_number, name):
        return VendorResult(verified=False, name_match_score=40, source="PRIMARY", latency_ms=10)
    monkeypatch.setattr(orchestrator, "call_vendor_a", mock_call_a)

    result = orchestrator.verify_identity("PAN", "ABCDE1234F", "Test User")
    assert result["verified"] is False
    assert result["source"] == "PRIMARY"
    assert result["fallback_used"] is False
    assert result["error_code"] == "VP2002"

def test_orchestrator_vendor_a_fails_fallback_to_b(monkeypatch):
    # Mock Vendor A to fail
    def mock_call_a(id_type, id_number, name):
        raise VendorFailureError("Vendor A offline")
    monkeypatch.setattr(orchestrator, "call_vendor_a", mock_call_a)

    # Mock Vendor B to succeed
    def mock_call_b(id_type, id_number, name):
        return VendorResult(verified=True, name_match_score=100, source="FALLBACK", latency_ms=15)
    monkeypatch.setattr(orchestrator, "call_vendor_b", mock_call_b)

    result = orchestrator.verify_identity("PAN", "ABCDE1234F", "Test User")
    assert result["verified"] is True
    assert result["source"] == "FALLBACK"
    assert result["fallback_used"] is True
    assert result["circuit_open"] is False
    assert result["error_code"] == "VP2001"

def test_orchestrator_vendor_a_times_out_fallback_to_b(monkeypatch):
    # Mock Vendor A to take too long
    def mock_call_a(id_type, id_number, name):
        time.sleep(1.0)
        return None
    monkeypatch.setattr(orchestrator, "call_vendor_a", mock_call_a)

    # Mock Vendor B to succeed
    def mock_call_b(id_type, id_number, name):
        return VendorResult(verified=True, name_match_score=90, source="FALLBACK", latency_ms=10)
    monkeypatch.setattr(orchestrator, "call_vendor_b", mock_call_b)

    # Use a low timeout budget in test config
    app_config = orchestrator._get_config()
    monkeypatch.setattr(app_config, "VENDOR_TIMEOUT_BUDGET_MS", 100) # 100ms budget

    result = orchestrator.verify_identity("PAN", "ABCDE1234F", "Test User")
    assert result["verified"] is True
    assert result["source"] == "FALLBACK"
    assert result["fallback_used"] is True
    assert result["error_code"] == "VP2001"

def test_orchestrator_double_failure_raises_exception(monkeypatch):
    # Mock Vendor A to fail
    def mock_call_a(id_type, id_number, name):
        raise VendorFailureError("A broke")
    monkeypatch.setattr(orchestrator, "call_vendor_a", mock_call_a)

    # Mock Vendor B to fail
    def mock_call_b(id_type, id_number, name):
        raise VendorFailureError("B broke")
    monkeypatch.setattr(orchestrator, "call_vendor_b", mock_call_b)

    with pytest.raises(AppVendorFailureError) as exc_info:
        orchestrator.verify_identity("PAN", "ABCDE1234F", "Test User")
    assert "Primary and fallback vendors failed" in str(exc_info.value)

def test_circuit_breaker_trips(monkeypatch):
    # Mock Vendor A to fail repeatedly
    def mock_call_a_fail(id_type, id_number, name):
        raise VendorFailureError("A is broken")
    monkeypatch.setattr(orchestrator, "call_vendor_a", mock_call_a_fail)

    # Mock Vendor B to succeed
    def mock_call_b(id_type, id_number, name):
        return VendorResult(verified=True, name_match_score=100, source="FALLBACK", latency_ms=10)
    monkeypatch.setattr(orchestrator, "call_vendor_b", mock_call_b)

    # Call orchestrator 3 times; it should fail on A and retry on B each time.
    # After the 3rd failure, the circuit should open.
    for i in range(3):
        res = orchestrator.verify_identity("PAN", "ABCDE1234F", f"User {i}")
        assert res["source"] == "FALLBACK"
        assert res["circuit_open"] is False

    # Now, the 4th call should trip the circuit breaker and call B directly without attempting A.
    # Let's verify that vendor_a is NOT called.
    a_called = False
    def mock_call_a_check(id_type, id_number, name):
        nonlocal a_called
        a_called = True
        return VendorResult(verified=True, name_match_score=100, source="PRIMARY", latency_ms=5)
    monkeypatch.setattr(orchestrator, "call_vendor_a", mock_call_a_check)

    res = orchestrator.verify_identity("PAN", "ABCDE1234F", "User 4")
    assert res["source"] == "FALLBACK"
    assert res["circuit_open"] is True
    assert a_called is False
