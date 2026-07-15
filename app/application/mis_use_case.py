import datetime as dt
from typing import Optional, List, Dict, Any
from app.domain.ports import APILogRepository, ClientRepository

class GetMISReportUseCase:
    def __init__(self, log_repo: APILogRepository, client_repo: ClientRepository):
        self.log_repo = log_repo
        self.client_repo = client_repo

    def get_usage_report(self, from_date: dt.datetime, to_date: dt.datetime, group_by: str, client_id: Optional[str] = None) -> List[Dict[str, Any]]:
        match_stage = {
            "created_at": {"$gte": from_date, "$lte": to_date}
        }
        if client_id:
            match_stage["client_id"] = client_id
            
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
        return self.log_repo.aggregate(pipeline)

    def get_errors_report(self, from_date: dt.datetime, to_date: dt.datetime, client_id: Optional[str] = None) -> List[Dict[str, Any]]:
        match_stage = {
            "created_at": {"$gte": from_date, "$lte": to_date}
        }
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
        return self.log_repo.aggregate(pipeline)

    def get_tps_report(self, client_id: str, date_str: str) -> Dict[str, Any]:
        start_date = dt.datetime.strptime(date_str, "%Y-%m-%d")
        end_date = start_date + dt.timedelta(days=1)
        
        match_stage = {
            "client_id": client_id,
            "created_at": {"$gte": start_date, "$lt": end_date}
        }
        
        # We need to count logs for this stage.
        # Let's count by matching logs via aggregation, which is safer and keeps Repository clean
        count_pipeline = [
            {"$match": match_stage},
            {"$count": "count"}
        ]
        count_res = self.log_repo.aggregate(count_pipeline)
        count_docs = count_res[0]["count"] if count_res else 0
        
        if count_docs == 0:
            return {
                "client_id": client_id,
                "date": date_str,
                "peak_tps": 0,
                "avg_tps": 0.0,
                "p95_latency_ms": 0
            }
            
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
        
        results = self.log_repo.aggregate(pipeline)
        data = results[0] if results else {}
        
        return {
            "client_id": client_id,
            "date": date_str,
            "peak_tps": data.get("peak_tps", 0),
            "avg_tps": data.get("avg_tps", 0.0),
            "p95_latency_ms": data.get("p95_latency_ms", 0)
        }

    def get_fallback_report(self, from_date: dt.datetime, to_date: dt.datetime) -> List[Dict[str, Any]]:
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
        return self.log_repo.aggregate(pipeline)

    def get_ips_report(self, client_id: str, from_date: dt.datetime, to_date: dt.datetime) -> List[Dict[str, Any]]:
        client = self.client_repo.get_by_client_id(client_id)
        whitelisted_ips = set(client.whitelisted_ips) if client else set()
        
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
        results = self.log_repo.aggregate(pipeline)
        
        for r in results:
            r["whitelisted"] = r["ip"] in whitelisted_ips
            
        return results
