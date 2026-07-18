from flask import Blueprint, request, jsonify, g, current_app
import time
import models
from utils.security import get_client_ip, require_client_auth, require_ip_whitelist
from utils.helpers import validate_verify_payload
from utils.errors import ValidationError, TpsLimitError
from services.rate_limiter import InMemoryRateLimiter
from services.vendor_service import verify_identity as run_vendor_verification
from services.log_service import LogService

verify_bp = Blueprint("verify", __name__)
rate_limiter = InMemoryRateLimiter()

@verify_bp.route("/api/v1/verify", methods=["POST"])
@require_client_auth
@require_ip_whitelist
@validate_verify_payload
def verify_identity_route():
    """
    POST /api/v1/verify
    Handles client authentication, IP whitelisting, request payload validation,
    rate limiting, vendor orchestration with fallback, and secure MongoDB log auditing.
    """
    start_time = time.time()
    
    # Context injected by decorators
    client_id = g.client_id
    user_id = g.user_id
    client_ip = g.client_ip
    
    # Retrieve limit from client context
    tps_limit = g.client.get("tps_limit", 2)
    
    # 1. Rate Limiting Check
    if rate_limiter.is_rate_limited(client_id, tps_limit):
        # Generate Log for Rate Limit Exceeded
        latency_ms = int((time.time() - start_time) * 1000)
        LogService.create_api_log(
            request_id=g.request_id,
            client_id=client_id,
            user_id=user_id,
            ip=client_ip,
            endpoint=request.path,
            id_type=g.id_type,
            raw_id_number=g.id_number,
            raw_name=g.name,
            http_status=429,
            error_code="VP4029",
            vendor_used=None,
            fallback_used=False,
            circuit_open=False,
            latency_ms=latency_ms
        )
        raise TpsLimitError(f"TPS limit of {tps_limit} exceeded for client '{client_id}'")

    # 2. Vendor Orchestration (handles primary, timeout, fallback, circuit breaker)
    try:
        res = run_vendor_verification(g.id_type, g.id_number, g.name)
        
        # Capture metrics from vendor orchestration
        vendor_used = "A" if res["source"] == "PRIMARY" else "B" if res["source"] == "FALLBACK" else None
        fallback_used = res["fallback_used"]
        circuit_open = res["circuit_open"]
        error_code = res["error_code"]
        verified = res["verified"]
        name_match_score = res["name_match_score"]
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # 3. Log request to MongoDB (secure masking inside LogService)
        LogService.create_api_log(
            request_id=g.request_id,
            client_id=client_id,
            user_id=user_id,
            ip=client_ip,
            endpoint=request.path,
            id_type=g.id_type,
            raw_id_number=g.id_number,
            raw_name=g.name,
            http_status=200,
            error_code=error_code,
            vendor_used=vendor_used,
            fallback_used=fallback_used,
            circuit_open=circuit_open,
            latency_ms=latency_ms
        )

        # 4. Standard Response Envelope
        return jsonify({
            "request_id": g.request_id,
            "status": "SUCCESS",
            "error_code": error_code,
            "data": {
                "verified": verified,
                "name_match_score": name_match_score,
                "source": res["source"]
            },
            "latency_ms": latency_ms
        }), 200

    except Exception as e:
        # Handle exceptions gracefully and ensure failed transactions are logged
        latency_ms = int((time.time() - start_time) * 1000)
        # Check if it was an AppError or unknown exception
        http_status = getattr(e, "http_status", 500)
        error_code = getattr(e, "error_code", "VP5000")
        
        LogService.create_api_log(
            request_id=g.request_id,
            client_id=client_id,
            user_id=user_id,
            ip=client_ip,
            endpoint=request.path,
            id_type=g.id_type,
            raw_id_number=g.id_number,
            raw_name=g.name,
            http_status=http_status,
            error_code=error_code,
            vendor_used=None,
            fallback_used=False,
            circuit_open=False,
            latency_ms=latency_ms
        )
        raise e
