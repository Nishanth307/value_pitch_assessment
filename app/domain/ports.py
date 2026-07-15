from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.domain.entities import Client, ClientUser, APILog, VerificationResult

class ClientRepository(ABC):
    @abstractmethod
    def get_by_api_key(self, api_key: str) -> Optional[Client]:
        pass

    @abstractmethod
    def get_by_client_id(self, client_id: str) -> Optional[Client]:
        pass

class ClientUserRepository(ABC):
    @abstractmethod
    def get_by_user_id_and_client_id(self, user_id: str, client_id: str) -> Optional[ClientUser]:
        pass

class APILogRepository(ABC):
    @abstractmethod
    def save(self, log: APILog) -> None:
        pass

    @abstractmethod
    def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pass

class RateLimiter(ABC):
    @abstractmethod
    def is_rate_limited(self, client_id: str, limit_tps: int) -> bool:
        pass

class IdentityVendor(ABC):
    @abstractmethod
    def verify(self, id_type: str, id_number: str, name: str) -> VerificationResult:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass
