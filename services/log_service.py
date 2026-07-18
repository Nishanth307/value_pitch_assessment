from datetime import datetime, timezone
import sys
from models import ApiLog
from utils.security import mask_id_number, mask_name, hash_value

class LogService:
    """Service to handle compliance-safe (PII masked/hashed) logging of requests to MongoDB."""
    @staticmethod
    def create_api_log(
        request_id: str,
        client_id: str,
        user_id: str,
        ip: str,
        endpoint: str,
        id_type: str,
        raw_id_number: str,
        raw_name: str,
        http_status: int,
        error_code: str,
        vendor_used: str,
        fallback_used: bool,
        circuit_open: bool,
        latency_ms: int
    ) -> None:
        """Constructs and inserts a secure, compliance-safe API log into MongoDB."""
        try:
            # Perform PII masking and hashing
            masked_id = mask_id_number(raw_id_number) if raw_id_number else None
            id_hash = hash_value(raw_id_number) if raw_id_number else None
            masked_nm = mask_name(raw_name) if raw_name else None
            name_hash = hash_value(raw_name) if raw_name else None

            log_document = {
                "request_id": request_id,
                "client_id": client_id,
                "user_id": user_id,
                "ip": ip,
                "endpoint": endpoint,
                "id_type": id_type,
                "masked_id_number": masked_id,
                "id_number_hash": id_hash,
                "masked_name": masked_nm,
                "name_hash": name_hash,
                "http_status": http_status,
                "error_code": error_code,
                "vendor_used": vendor_used,
                "fallback_used": fallback_used,
                "circuit_open": circuit_open,
                "latency_ms": latency_ms,
                "created_at": datetime.now(timezone.utc)
            }

            ApiLog.insert_log(log_document)
        except Exception as e:
            # Prevent logging failures from crashing the main API flow
            print(f"ERROR: Failed to save audit log: {e}", file=sys.stderr)
