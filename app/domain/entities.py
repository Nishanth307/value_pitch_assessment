from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class Client:
    client_id: str
    name: str
    api_key: str
    whitelisted_ips: List[str]
    tps_limit: int
    status: str = "active"

    def is_active(self) -> bool:
        return self.status == "active"

    def is_ip_whitelisted(self, ip: str) -> bool:
        return ip in self.whitelisted_ips

@dataclass
class ClientUser:
    user_id: str
    client_id: str
    name: str
    status: str = "active"

    def is_active(self) -> bool:
        return self.status == "active"

@dataclass
class APILog:
    request_id: str
    client_id: Optional[str]
    user_id: Optional[str]
    ip: str
    endpoint: str
    id_type: Optional[str]
    masked_id_number: Optional[str]
    id_number_hash: Optional[str]
    masked_name: Optional[str]
    name_hash: Optional[str]
    http_status: int
    error_code: str
    vendor_used: Optional[str]
    fallback_used: bool
    circuit_open: bool
    latency_ms: int
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "client_id": self.client_id,
            "user_id": self.user_id,
            "ip": self.ip,
            "endpoint": self.endpoint,
            "id_type": self.id_type,
            "masked_id_number": self.masked_id_number,
            "id_number_hash": self.id_number_hash,
            "masked_name": self.masked_name,
            "name_hash": self.name_hash,
            "http_status": self.http_status,
            "error_code": self.error_code,
            "vendor_used": self.vendor_used,
            "fallback_used": self.fallback_used,
            "circuit_open": self.circuit_open,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at
        }

@dataclass
class VerificationResult:
    verified: bool
    name_match_score: Optional[int]
    source: str
    fallback_used: bool
    circuit_open: bool
    error_code: str
    latency_ms: int
