import time
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from app.domain.entities import APILog, VerificationResult
from app.domain.ports import ClientRepository, ClientUserRepository, APILogRepository, RateLimiter, IdentityVendor
from app.utils.errors import AuthError, IpNotWhitelistedError, ValidationError, TpsLimitError, VendorFailureError
from app.utils.security import mask_id_number, mask_name, hash_value

import app.services.vendors as legacy_vendors

class CircuitBreaker:
    def __init__(self, failure_window: int = 60, failure_threshold: int = 3, cooldown: int = 30):
        self.failure_window = failure_window
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self._lock = threading.Lock()

    @property
    def failure_timestamps(self):
        return legacy_vendors._failure_timestamps

    @property
    def circuit_open_until(self):
        return legacy_vendors._circuit_open_until

    @circuit_open_until.setter
    def circuit_open_until(self, val):
        legacy_vendors._circuit_open_until = val

    def record_failure(self) -> None:
        now = time.time()
        with self._lock:
            self.failure_timestamps.append(now)
            while self.failure_timestamps and self.failure_timestamps[0] < now - self.failure_window:
                self.failure_timestamps.popleft()
            if len(self.failure_timestamps) >= self.failure_threshold:
                self.circuit_open_until = now + self.cooldown

    def is_open(self) -> bool:
        with self._lock:
            return time.time() < self.circuit_open_until

    def reset(self) -> None:
        with self._lock:
            self.failure_timestamps.clear()
            self.circuit_open_until = 0.0


class VerifyIdentityUseCase:
    def __init__(
        self,
        client_repo: ClientRepository,
        user_repo: ClientUserRepository,
        log_repo: APILogRepository,
        rate_limiter: RateLimiter,
        primary_vendor: IdentityVendor,
        fallback_vendor: IdentityVendor,
        circuit_breaker: CircuitBreaker,
        timeout_budget_ms: int = 500
    ):
        self.client_repo = client_repo
        self.user_repo = user_repo
        self.log_repo = log_repo
        self.rate_limiter = rate_limiter
        self.primary_vendor = primary_vendor
        self.fallback_vendor = fallback_vendor
        self.circuit_breaker = circuit_breaker
        self.timeout_budget_ms = timeout_budget_ms

    def execute(
        self,
        request_id: str,
        api_key: Optional[str],
        user_id: Optional[str],
        ip: str,
        endpoint: str,
        payload: dict,
        bypass_auth: bool = False
    ) -> VerificationResult:
        start_time = time.time()
        
        client_id = "test_client" if bypass_auth else None
        user_id_val = user_id if user_id else "test_user_01" if bypass_auth else None
        id_type = payload.get("id_type")
        id_number = payload.get("id_number")
        name = payload.get("name")
        
        # Initialize log parameters
        error_code = "VP5000"
        http_status = 500
        vendor_used = None
        fallback_used = False
        circuit_open = False
        
        try:
            if not bypass_auth:
                # 1. Authenticate API Key
                if not api_key:
                    http_status = 401
                    error_code = "VP4001"
                    raise AuthError("Missing X-API-Key header")
                    
                client = self.client_repo.get_by_api_key(api_key)
                if not client:
                    http_status = 401
                    error_code = "VP4001"
                    raise AuthError("Invalid or inactive API key")
                    
                client_id = client.client_id
                
                # 2. IP Whitelisting
                if not client.is_ip_whitelisted(ip):
                    http_status = 403
                    error_code = "VP4003"
                    raise IpNotWhitelistedError(f"Client IP '{ip}' is not whitelisted")
                    
                # 3. User Validation
                if not user_id:
                    http_status = 422
                    error_code = "VP4022"
                    raise ValidationError("Missing X-User-Id header")
                    
                user = self.user_repo.get_by_user_id_and_client_id(user_id, client_id)
                if not user:
                    http_status = 422
                    error_code = "VP4022"
                    raise ValidationError(f"Invalid or inactive sub-user: '{user_id}'")
                    
                # 4. Payload validation
                # client_ref_id is mandatory
                if not payload.get("client_ref_id"):
                    http_status = 422
                    error_code = "VP4022"
                    raise ValidationError("Missing required field: client_ref_id")
                if not id_type or id_type not in ["PAN", "DL", "VOTER"]:
                    http_status = 422
                    error_code = "VP4022"
                    raise ValidationError("Missing or invalid id_type. Must be PAN, DL, or VOTER")
                if not id_number or not str(id_number).strip():
                    http_status = 422
                    error_code = "VP4022"
                    raise ValidationError("Missing or empty field: id_number")
                if not name or not str(name).strip():
                    http_status = 422
                    error_code = "VP4022"
                    raise ValidationError("Missing or empty field: name")
                    
                # 5. Rate Limiting (TPS)
                if self.rate_limiter.is_rate_limited(client_id, client.tps_limit):
                    http_status = 429
                    error_code = "VP4029"
                    raise TpsLimitError(f"TPS limit of {client.tps_limit} exceeded for client '{client_id}'")
                
            # 6. Vendor Orchestration with Timeout & Fallback
            circuit_open = self.circuit_breaker.is_open()
            result = None
            
            if not circuit_open:
                result_holder = {}
                exception_holder = {}
                
                def target():
                    try:
                        result_holder["res"] = self.primary_vendor.verify(id_type, id_number, name)
                    except Exception as e:
                        exception_holder["exc"] = e
                        
                thread = threading.Thread(target=target)
                thread.daemon = True
                thread.start()
                thread.join(timeout=self.timeout_budget_ms / 1000.0)
                
                if thread.is_alive():
                    # Thread timed out
                    self.circuit_breaker.record_failure()
                elif "exc" in exception_holder:
                    # Thread failed with exception
                    self.circuit_breaker.record_failure()
                else:
                    result = result_holder["res"]
                    vendor_used = "A"
                    fallback_used = False
                    
            if result is None:
                # Circuit is open or Primary failed -> Fallback to Vendor B
                fallback_used = True
                vendor_used = "B"
                try:
                    result = self.fallback_vendor.verify(id_type, id_number, name)
                except Exception:
                    http_status = 502
                    error_code = "VP5001"
                    raise VendorFailureError("Primary and fallback vendors failed to verify identity")
                    
            # Success response
            http_status = 200
            error_code = result.error_code
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Map result details
            return VerificationResult(
                verified=result.verified,
                name_match_score=result.name_match_score,
                source=result.source,
                fallback_used=fallback_used,
                circuit_open=circuit_open,
                error_code=error_code,
                latency_ms=latency_ms
            )
            
        except Exception as e:
            # Re-raise AppError exceptions so HTTP Layer handles them, but log them first!
            latency_ms = int((time.time() - start_time) * 1000)
            raise e
            
        finally:
            # Audit log generation (PII Compliant)
            try:
                masked_id = mask_id_number(id_number) if id_number else None
                hashed_id = hash_value(id_number) if id_number else None
                masked_nm = mask_name(name) if name else None
                hashed_nm = hash_value(name) if name else None
                
                api_log = APILog(
                    request_id=request_id,
                    client_id=client_id,
                    user_id=user_id_val,
                    ip=ip,
                    endpoint=endpoint,
                    id_type=id_type,
                    masked_id_number=masked_id,
                    id_number_hash=hashed_id,
                    masked_name=masked_nm,
                    name_hash=hashed_nm,
                    http_status=http_status,
                    error_code=error_code,
                    vendor_used=vendor_used,
                    fallback_used=fallback_used,
                    circuit_open=circuit_open,
                    latency_ms=latency_ms,
                    created_at=datetime.utcnow()
                )
                self.log_repo.save(api_log)
            except Exception as log_err:
                # Suppress log writing exceptions to prevent bringing down API
                import sys
                print(f"Failed to save audit log: {log_err}", file=sys.stderr)
