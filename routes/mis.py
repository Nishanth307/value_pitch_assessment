import csv
import io
import datetime as dt
from flask import Blueprint, request, jsonify, make_response, current_app
from utils.errors import AuthError, ValidationError
from utils.helpers import parse_iso_date
import models

mis_bp = Blueprint("mis", __name__)

@mis_bp.before_request
def enforce_admin_auth():
    """Verify that the caller has a valid Admin API Key."""
    admin_key = request.headers.get("X-Admin-Key")
    expected_key = current_app.config.get("ADMIN_API_KEY")
    if not admin_key or admin_key != expected_key:
        raise AuthError("Missing or invalid Admin API key")

@mis_bp.route("/api/v1/mis/usage", methods=["GET"])
def usage_report():
    """
    GET /api/v1/mis/usage
    Compiles request usage statistics aggregated by client, user, or day.
    """
    from_date = parse_iso_date(request.args.get("from"), "from")
    to_date = parse_iso_date(request.args.get("to"), "to")
    group_by = request.args.get("group_by", "client")
    client_id = request.args.get("client_id")
    fmt = request.args.get("format", "json")
    
    if group_by not in {"client", "user", "day"}:
        raise ValidationError("Parameter 'group_by' must be one of: client, user, day")
        
    # Match stage to filter by date range and optional client_id
    match_stage = {"created_at": {"$gte": from_date, "$lte": to_date}}
    if client_id:
        match_stage["client_id"] = client_id
        
    # Set grouping key depending on request
    if group_by == "client":
        group_id = "$client_id"
        dimension_key = "client_id"
    elif group_by == "user":
        group_id = "$user_id"
        dimension_key = "user_id"
    else:  # day
        group_id = {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}
        dimension_key = "day"
        
    pipeline = [
        {"$match": match_stage},
        {
            "$group": {
                "_id": group_id,
                "total": {"$sum": 1},
                "success": {
                    "$sum": {
                        "$cond": [{"$in": ["$error_code", ["VP2000", "VP2001"]]}, 1, 0]
                    }
                },
                "success_via_fallback": {
                    "$sum": {
                        "$cond": [{"$eq": ["$error_code", "VP2001"]}, 1, 0]
                    }
                },
                "not_verified": {
                    "$sum": {
                        "$cond": [{"$eq": ["$error_code", "VP2002"]}, 1, 0]
                    }
                },
                "failed": {
                    "$sum": {
                        "$cond": [{"$not": [{"$in": ["$error_code", ["VP2000", "VP2001", "VP2002"]]}]}, 1, 0]
                    }
                },
                "avg_latency_ms": {"$avg": "$latency_ms"}
            }
        },
        {
            "$project": {
                "_id": 0,
                dimension_key: "$_id",
                "total": 1,
                "success": 1,
                "success_via_fallback": 1,
                "not_verified": 1,
                "failed": 1,
                "avg_latency_ms": {"$round": ["$avg_latency_ms", 2]}
            }
        }
    ]
    
    results = models.ApiLog.run_aggregation(pipeline)
    
    # Export to CSV if format is specified
    if fmt == "csv":
        si = io.StringIO()
        cw = csv.writer(si)
        dimension_key_header = "day" if group_by == "day" else f"{group_by}_id"
        headers = [dimension_key_header, "total", "success", "success_via_fallback", "not_verified", "failed", "avg_latency_ms"]
        cw.writerow(headers)
        for r in results:
            # Map dimension_key to match csv header keys
            r_val = r.copy()
            if dimension_key != dimension_key_header:
                r_val[dimension_key_header] = r_val.get(dimension_key)
            cw.writerow([r_val.get(h) for h in headers])
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
    """
    GET /api/v1/mis/errors
    Aggregates errors occurring within a given timeframe.
    """
    from_date = parse_iso_date(request.args.get("from"), "from")
    to_date = parse_iso_date(request.args.get("to"), "to")
    client_id = request.args.get("client_id")
    fmt = request.args.get("format", "json")
    
    match_stage = {"created_at": {"$gte": from_date, "$lte": to_date}}
    if client_id:
        match_stage["client_id"] = client_id
        
    pipeline = [
        {"$match": match_stage},
        {
            "$group": {
                "_id": {
                    "client_id": "$client_id",
                    "error_code": "$error_code"
                },
                "count": {"$sum": 1}
            }
        },
        {
            "$project": {
                "_id": 0,
                "client_id": "$_id.client_id",
                "error_code": "$_id.error_code",
                "count": 1
            }
        }
    ]
    
    results = models.ApiLog.run_aggregation(pipeline)
    
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
    """
    GET /api/v1/mis/tps
    Computes peak TPS, average TPS, and 95th percentile latency (p95) on a specific date.
    """
    client_id = request.args.get("client_id")
    date_str = request.args.get("date")
    
    if not client_id:
        raise ValidationError("Query parameter 'client_id' is required")
    if not date_str:
        raise ValidationError("Query parameter 'date' is required")
        
    try:
        start_date = dt.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValidationError("Parameter 'date' must be in YYYY-MM-DD format")
        
    end_date = start_date + dt.timedelta(days=1)
    
    match_stage = {
        "client_id": client_id,
        "created_at": {"$gte": start_date, "$lt": end_date}
    }
    
    # Check if logs exist
    count = models.ApiLog.count_logs(match_stage)
    if count == 0:
        return jsonify({
            "status": "SUCCESS",
            "data": {
                "client_id": client_id,
                "date": date_str,
                "peak_tps": 0,
                "avg_tps": 0.0,
                "p95_latency_ms": 0
            }
        })
        
    pipeline = [
        {"$match": match_stage},
        {
            "$group": {
                "_id": {
                    "$dateToString": {"format": "%Y-%m-%dT%H:%M:%S", "date": "$created_at"}
                },
                "tps": {"$sum": 1},
                "latencies": {"$push": "$latency_ms"}
            }
        },
        {
            "$group": {
                "_id": None,
                "peak_tps": {"$max": "$tps"},
                "total_requests": {"$sum": "$tps"},
                "seconds_with_traffic": {"$sum": 1},
                "all_latencies": {"$push": "$latencies"}
            }
        },
        {
            "$project": {
                "peak_tps": 1,
                "total_requests": 1,
                "seconds_with_traffic": 1,
                "flat_latencies": {
                    "$reduce": {
                        "input": "$all_latencies",
                        "initialValue": [],
                        "in": {"$concatArrays": ["$$value", "$$this"]}
                    }
                }
            }
        },
        {
            "$project": {
                "peak_tps": 1,
                "avg_tps": {"$divide": ["$total_requests", "$seconds_with_traffic"]},
                "sorted_latencies": {
                    "$sortArray": {"input": "$flat_latencies", "sortBy": 1}
                }
            }
        },
        {
            "$project": {
                "peak_tps": 1,
                "avg_tps": {"$round": ["$avg_tps", 2]},
                "p95_latency_ms": {
                    "$arrayElemAt": [
                        "$sorted_latencies",
                        {"$floor": {"$multiply": [0.95, {"$size": "$sorted_latencies"}]}}
                    ]
                }
            }
        }
    ]
    
    results = models.ApiLog.run_aggregation(pipeline)
    data = results[0] if results else {}
    
    return jsonify({
        "status": "SUCCESS",
        "data": {
            "client_id": client_id,
            "date": date_str,
            "peak_tps": data.get("peak_tps", 0),
            "avg_tps": data.get("avg_tps", 0.0),
            "p95_latency_ms": data.get("p95_latency_ms", 0)
        }
    })

@mis_bp.route("/api/v1/mis/fallback", methods=["GET"])
def fallback_report():
    """
    GET /api/v1/mis/fallback
    Computes fallback usage ratio for each client.
    """
    from_date = parse_iso_date(request.args.get("from"), "from")
    to_date = parse_iso_date(request.args.get("to"), "to")
    
    pipeline = [
        {"$match": {"created_at": {"$gte": from_date, "$lte": to_date}}},
        {
            "$group": {
                "_id": "$client_id",
                "total_success": {
                    "$sum": {
                        "$cond": [{"$in": ["$error_code", ["VP2000", "VP2001"]]}, 1, 0]
                    }
                },
                "served_by_fallback": {
                    "$sum": {
                        "$cond": [{"$eq": ["$error_code", "VP2001"]}, 1, 0]
                    }
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "client_id": "$_id",
                "total_success": 1,
                "served_by_fallback": 1,
                "fallback_ratio_pct": {
                    "$round": [
                        {
                            "$cond": [
                                {"$eq": ["$total_success", 0]},
                                0.0,
                                {"$multiply": [{"$divide": ["$served_by_fallback", "$total_success"]}, 100.0]}
                            ]
                        },
                        2
                    ]
                }
            }
        }
    ]
    
    results = models.ApiLog.run_aggregation(pipeline)
    return jsonify({
        "status": "SUCCESS",
        "data": results
    })

@mis_bp.route("/api/v1/mis/ips", methods=["GET"])
def ips_report():
    """
    GET /api/v1/mis/ips
    Returns IP traffic analysis for a client.
    """
    client_id = request.args.get("client_id")
    from_date = parse_iso_date(request.args.get("from"), "from")
    to_date = parse_iso_date(request.args.get("to"), "to")
    
    if not client_id:
        raise ValidationError("Query parameter 'client_id' is required")
        
    client = models.Client.find_by_client_id(client_id)
    whitelisted_ips = set(client.get("whitelisted_ips", [])) if client else set()
    
    pipeline = [
        {
            "$match": {
                "client_id": client_id,
                "created_at": {"$gte": from_date, "$lte": to_date}
            }
        },
        {
            "$group": {
                "_id": "$ip",
                "total_hits": {"$sum": 1},
                "blocked_hits": {
                    "$sum": {
                        "$cond": [{"$eq": ["$error_code", "VP4003"]}, 1, 0]
                    }
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "ip": "$_id",
                "total_hits": 1,
                "blocked_hits": 1
            }
        }
    ]
    
    results = models.ApiLog.run_aggregation(pipeline)
    
    for r in results:
        r["whitelisted"] = r["ip"] in whitelisted_ips
        
    return jsonify({
        "status": "SUCCESS",
        "data": results
    })
