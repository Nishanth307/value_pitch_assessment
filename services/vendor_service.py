import time
import random
import threading
from collections import deque
from dataclasses import dataclass
from flask import current_app

# Custom exceptions for vendor status simulation
class VendorTimeoutError(Exception):
    pass

class VendorFailureError(Exception):
    pass

@dataclass
class VendorResult:
    """Dataclass holding verification results from a vendor."""
    verified: bool
    name_match_score: int
    source: str
    latency_ms: int

# Module-level variables for tracking primary vendor failures (used by circuit breaker)
_failure_timestamps = deque()
_circuit_open_until = 0.0
_circuit_lock = threading.Lock()

def _get_config():
    """Retrieve config values from Flask's current_app context or use defaults."""
    try:
        if current_app:
            return current_app.config
    except RuntimeError:
        pass
    from config import Config
    return Config

def _get_val(cfg, key, default):
    """Safely get config values from either current_app.config or Config class."""
    if hasattr(cfg, "get"):
        return cfg.get(key, default)
    return getattr(cfg, key, default)

def call_vendor_a(id_type: str, id_number: str, name: str) -> VendorResult:
    """Simulates Vendor A (Primary Vendor) with configurable failures and timeouts."""
    cfg = _get_config()
    min_lat = _get_val(cfg, "VENDOR_MIN_LATENCY_MS", 100)
    max_lat = _get_val(cfg, "VENDOR_MAX_LATENCY_MS", 1000)
    fail_rate = _get_val(cfg, "VENDOR_A_FAILURE_RATE", 0.1)
    timeout_rate = _get_val(cfg, "VENDOR_A_TIMEOUT_RATE", 0.1)

    # Simulate network latency
    latency_ms = int(random.uniform(min_lat, max_lat))
    time.sleep(latency_ms / 1000.0)

    # Determine randomized outcome
    rand_val = random.random()
    if rand_val < timeout_rate:
        raise VendorTimeoutError("Vendor A connection timed out")
    elif rand_val < (timeout_rate + fail_rate):
        raise VendorFailureError("Vendor A internal system error")

    # Hardcoded test case: If ID number ends with '99', return unverified (name mismatch / not found)
    if id_number.endswith("99"):
        return VendorResult(verified=False, name_match_score=45, source="PRIMARY", latency_ms=latency_ms)
    
    # Calculate score based on name length odd/even to make it dynamic
    name_score = 100 if len(name) % 2 == 0 else 90
    return VendorResult(verified=True, name_match_score=name_score, source="PRIMARY", latency_ms=latency_ms)

def call_vendor_b(id_type: str, id_number: str, name: str) -> VendorResult:
    """Simulates Vendor B (Fallback Vendor) - highly reliable, no configurable failures."""
    cfg = _get_config()
    min_lat = _get_val(cfg, "VENDOR_MIN_LATENCY_MS", 100)
    max_lat = _get_val(cfg, "VENDOR_MAX_LATENCY_MS", 1000)

    latency_ms = int(random.uniform(min_lat, max_lat))
    time.sleep(latency_ms / 1000.0)

    # Vendor B has a tiny baseline failure rate (2% timeout, 3% system failure)
    rand_val = random.random()
    if rand_val < 0.02:
        raise VendorTimeoutError("Vendor B connection timed out")
    elif rand_val < 0.05:
        raise VendorFailureError("Vendor B internal system error")

    if id_number.endswith("99"):
        return VendorResult(verified=False, name_match_score=45, source="FALLBACK", latency_ms=latency_ms)

    name_score = 100 if len(name) % 2 == 0 else 90
    return VendorResult(verified=True, name_match_score=name_score, source="FALLBACK", latency_ms=latency_ms)

def verify_identity(id_type: str, id_number: str, name: str) -> dict:
    """
    Orchestrates the identity verification process:
    1. Checks Circuit Breaker state. If open, skips Vendor A.
    2. Calls Vendor A in a background thread.
    3. Enforces a timeout budget on Vendor A.
    4. Handles Vendor A failures/timeouts by updating the Circuit Breaker and falling back to Vendor B.
    """
    global _circuit_open_until
    cfg = _get_config()
    timeout_budget_ms = _get_val(cfg, "VENDOR_TIMEOUT_BUDGET_MS", 500)

    start_time = time.time()
    now = time.time()
    circuit_open = now < _circuit_open_until

    result = None
    fallback_used = False
    error_code = "VP5000"

    # If the circuit is closed, try Vendor A (Primary)
    if not circuit_open:
        result_holder = {}
        exception_holder = {}

        def worker():
            try:
                result_holder["res"] = call_vendor_a(id_type, id_number, name)
            except Exception as e:
                exception_holder["exc"] = e

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout_budget_ms / 1000.0)

        if thread.is_alive():
            # Thread is still running -> Timeout occurred
            _record_primary_failure()
        elif "exc" in exception_holder:
            # Vendor A failed with an exception
            _record_primary_failure()
        else:
            # Successfully obtained a result from Vendor A
            result = result_holder.get("res")
            error_code = "VP2000" if result.verified else "VP2002"

    # If circuit was open, or Vendor A timed out/failed, run Vendor B
    if result is None:
        fallback_used = True
        if circuit_open:
            # Explicitly log if we bypassed A because the circuit was already open
            pass
        else:
            # Primary failed, now falling back
            pass

        try:
            result = call_vendor_b(id_type, id_number, name)
            error_code = "VP2001" if result.verified else "VP2002"
        except Exception:
            # Both primary and fallback vendors failed
            from utils.errors import VendorFailureError as AppVendorFailureError
            raise AppVendorFailureError("Primary and fallback vendors failed to verify identity")

    total_latency_ms = int((time.time() - start_time) * 1000)

    return {
        "verified": result.verified,
        "name_match_score": result.name_match_score,
        "source": result.source,
        "fallback_used": fallback_used,
        "circuit_open": circuit_open,
        "error_code": error_code,
        "latency_ms": total_latency_ms
    }

def _record_primary_failure(window: int = 60, threshold: int = 3, cooldown: int = 30):
    """Logs a primary vendor failure and trips circuit if failure threshold reached."""
    global _circuit_open_until
    now = time.time()
    with _circuit_lock:
        _failure_timestamps.append(now)
        # Prune old timestamps outside the sliding window
        while _failure_timestamps and _failure_timestamps[0] < now - window:
            _failure_timestamps.popleft()
        
        # If failures in window exceed threshold, trip the circuit breaker
        if len(_failure_timestamps) >= threshold:
            _circuit_open_until = now + cooldown
