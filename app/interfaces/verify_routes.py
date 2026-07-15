import uuid
import time
from flask import Blueprint, request, jsonify, current_app, g
from app.utils.security import get_client_ip

verify_bp = Blueprint("verify", __name__)

@verify_bp.before_request
def record_start_time():
    g.start_time = time.time()
    g.request_id = f"req_{uuid.uuid4().hex[:8]}"

@verify_bp.route("/api/v1/verify", methods=["POST"])
def verify_identity():
    api_key = request.headers.get("X-API-Key")
    user_id = request.headers.get("X-User-Id")
    ip = get_client_ip()
    endpoint = request.path
    
    # Store in g for logging/middleware compatibility
    g.request_id = getattr(g, "request_id", None) or f"req_{uuid.uuid4().hex[:8]}"
    
    payload = request.get_json(silent=True) or {}
    
    # Extract params to g for compatibility with tests/helpers if needed
    g.id_type = payload.get("id_type")
    g.id_number = payload.get("id_number")
    g.name = payload.get("name")
    g.user_id = user_id
    
    verify_use_case = current_app.container.verify_use_case
    result = verify_use_case.execute(
        request_id=g.request_id,
        api_key=api_key,
        user_id=user_id,
        ip=ip,
        endpoint=endpoint,
        payload=payload
    )
    
    # Expose vendor metrics to g for logging/after_request compatibility if any
    g.vendor_used = "A" if result.source == "PRIMARY" else "B" if result.source == "FALLBACK" else None
    g.fallback_used = result.fallback_used
    g.circuit_open = result.circuit_open
    
    return jsonify({
        "request_id": g.request_id,
        "status": "SUCCESS",
        "error_code": result.error_code,
        "data": {
            "verified": result.verified,
            "name_match_score": result.name_match_score,
            "source": result.source
        },
        "latency_ms": result.latency_ms
    })
