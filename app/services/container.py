from app.extensions import mongo
from app.infrastructure.mongo_repositories import MongoClientRepository, MongoClientUserRepository, MongoAPILogRepository
from app.infrastructure.in_memory_limiter import InMemoryRateLimiter
from app.infrastructure.vendor_adapters import LegacyVendorAdapterA, LegacyVendorAdapterB
from app.application.verify_use_case import VerifyIdentityUseCase, CircuitBreaker
from app.application.mis_use_case import GetMISReportUseCase

class Container:
    def __init__(self, app_config):
        def get_val(key, default):
            if hasattr(app_config, "get"):
                val = app_config.get(key)
                return val if val is not None else default
            val = getattr(app_config, key, None)
            return val if val is not None else default

        # Repositories
        self.client_repo = MongoClientRepository(mongo.db)
        self.user_repo = MongoClientUserRepository(mongo.db)
        self.log_repo = MongoAPILogRepository(mongo.db)
        
        # Rate Limiter (shared)
        self.rate_limiter = InMemoryRateLimiter()
        
        # Circuit Breaker (shared)
        self.circuit_breaker = CircuitBreaker()
        
        # Vendor Adapters
        self.primary_vendor = LegacyVendorAdapterA()
        self.fallback_vendor = LegacyVendorAdapterB()
        
        # Use Cases
        self.verify_use_case = VerifyIdentityUseCase(
            client_repo=self.client_repo,
            user_repo=self.user_repo,
            log_repo=self.log_repo,
            rate_limiter=self.rate_limiter,
            primary_vendor=self.primary_vendor,
            fallback_vendor=self.fallback_vendor,
            circuit_breaker=self.circuit_breaker,
            timeout_budget_ms=get_val("VENDOR_TIMEOUT_BUDGET_MS", 500)
        )
        
        self.get_mis_report_use_case = GetMISReportUseCase(
            log_repo=self.log_repo,
            client_repo=self.client_repo
        )
