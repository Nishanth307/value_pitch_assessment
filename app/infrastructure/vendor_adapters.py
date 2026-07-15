import time
import random
from app.domain.entities import VerificationResult
from app.domain.ports import IdentityVendor
import app.services.vendors as legacy_vendors

# Legacy exceptions
from app.services.vendors import VendorTimeoutError, VendorFailureError

class LegacyVendorAdapterA(IdentityVendor):
    @property
    def name(self) -> str:
        return "PRIMARY"

    def verify(self, id_type: str, id_number: str, name: str) -> VerificationResult:
        res = legacy_vendors.call_vendor_a(id_type, id_number, name)
        return VerificationResult(
            verified=res.verified,
            name_match_score=res.name_match_score,
            source="PRIMARY",
            fallback_used=False,
            circuit_open=False,
            error_code="VP2000" if res.verified else "VP2002",
            latency_ms=res.latency_ms
        )

class LegacyVendorAdapterB(IdentityVendor):
    @property
    def name(self) -> str:
        return "FALLBACK"

    def verify(self, id_type: str, id_number: str, name: str) -> VerificationResult:
        res = legacy_vendors.call_vendor_b(id_type, id_number, name)
        return VerificationResult(
            verified=res.verified,
            name_match_score=res.name_match_score,
            source="FALLBACK",
            fallback_used=True,
            circuit_open=False,
            error_code="VP2001" if res.verified else "VP2002",
            latency_ms=res.latency_ms
        )
