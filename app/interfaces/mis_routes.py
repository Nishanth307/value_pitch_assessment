import csv
import io
from flask import Blueprint, request, jsonify, make_response, current_app
from app.config import Config
from app.utils.errors import AuthError, ValidationError
from app.utils.validators import parse_iso_date

mis_bp = Blueprint("mis", __name__)

def require_admin_auth():
    admin_key = request.headers.get("X-Admin-Key")
    cfg = current_app.config
    expected_key = cfg.get("ADMIN_API_KEY")
    if not admin_key or admin_key != expected_key:
        raise AuthError("Missing or invalid Admin API key")

@mis_bp.before_request
def enforce_admin_auth():
    require_admin_auth()

@mis_bp.route("/api/v1/mis/usage", methods=["GET"])
def usage_report():
    from_date = parse_iso_date(request.args.get("from"), "from")
    to_date = parse_iso_date(request.args.get("to"), "to")
    group_by = request.args.get("group_by", "client")
    client_id = request.args.get("client_id")
    fmt = request.args.get("format", "json")
    
    if group_by not in {"client", "user", "day"}:
        raise ValidationError("Parameter 'group_by' must be one of: client, user, day")
        
    mis_use_case = current_app.container.get_mis_report_use_case
    results = mis_use_case.get_usage_report(from_date, to_date, group_by, client_id)
    
    if fmt == "csv":
        si = io.StringIO()
        cw = csv.writer(si)
        dimension_key = "day" if group_by == "day" else f"{group_by}_id"
        headers = [dimension_key, "total", "success", "success_via_fallback", "not_verified", "failed", "avg_latency_ms"]
        cw.writerow(headers)
        for r in results:
            cw.writerow([r.get(h) for h in headers])
        response = make_response(si.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=usage_report_{group_by}.csv"
        response.headers["Content-Type"] = "text/csv"
        return response
        
    return jsonify({
        "status": "SUCCESS",
        "data": results
    })

@mis_bp.route("/api/v1/mis/errors", methods=["GET"])
def errors_report():
    from_date = parse_iso_date(request.args.get("from"), "from")
    to_date = parse_iso_date(request.args.get("to"), "to")
    client_id = request.args.get("client_id")
    fmt = request.args.get("format", "json")
    
    mis_use_case = current_app.container.get_mis_report_use_case
    results = mis_use_case.get_errors_report(from_date, to_date, client_id)
    
    if fmt == "csv":
        si = io.StringIO()
        cw = csv.writer(si)
        headers = ["client_id", "error_code", "count"]
        cw.writerow(headers)
        for r in results:
            cw.writerow([r.get(h) for h in headers])
        response = make_response(si.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=errors_report.csv"
        response.headers["Content-Type"] = "text/csv"
        return response
        
    return jsonify({
        "status": "SUCCESS",
        "data": results
    })

@mis_bp.route("/api/v1/mis/tps", methods=["GET"])
def tps_report():
    client_id = request.args.get("client_id")
    date_str = request.args.get("date")
    
    if not client_id:
        raise ValidationError("Query parameter 'client_id' is required")
    if not date_str:
        raise ValidationError("Query parameter 'date' is required")
        
    mis_use_case = current_app.container.get_mis_report_use_case
    report_data = mis_use_case.get_tps_report(client_id, date_str)
    
    return jsonify({
        "status": "SUCCESS",
        "data": report_data
    })

@mis_bp.route("/api/v1/mis/fallback", methods=["GET"])
def fallback_report():
    from_date = parse_iso_date(request.args.get("from"), "from")
    to_date = parse_iso_date(request.args.get("to"), "to")
    
    mis_use_case = current_app.container.get_mis_report_use_case
    results = mis_use_case.get_fallback_report(from_date, to_date)
    return jsonify({
        "status": "SUCCESS",
        "data": results
    })

@mis_bp.route("/api/v1/mis/ips", methods=["GET"])
def ips_report():
    client_id = request.args.get("client_id")
    from_date = parse_iso_date(request.args.get("from"), "from")
    to_date = parse_iso_date(request.args.get("to"), "to")
    
    if not client_id:
        raise ValidationError("Query parameter 'client_id' is required")
        
    mis_use_case = current_app.container.get_mis_report_use_case
    results = mis_use_case.get_ips_report(client_id, from_date, to_date)
        
    return jsonify({
        "status": "SUCCESS",
        "data": results
    })
