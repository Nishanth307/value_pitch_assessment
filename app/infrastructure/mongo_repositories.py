from typing import Optional, List, Dict, Any
from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING
from app.domain.entities import Client, ClientUser, APILog
from app.domain.ports import ClientRepository, ClientUserRepository, APILogRepository

class MongoClientRepository(ClientRepository):
    def __init__(self, db: Database):
        self.collection = db["clients"]

    def get_by_api_key(self, api_key: str) -> Optional[Client]:
        doc = self.collection.find_one({"api_key": api_key, "status": "active"})
        if not doc:
            return None
        return Client(
            client_id=doc["client_id"],
            name=doc["name"],
            api_key=doc["api_key"],
            whitelisted_ips=doc["whitelisted_ips"],
            tps_limit=doc["tps_limit"],
            status=doc.get("status", "active")
        )

    def get_by_client_id(self, client_id: str) -> Optional[Client]:
        doc = self.collection.find_one({"client_id": client_id})
        if not doc:
            return None
        return Client(
            client_id=doc["client_id"],
            name=doc["name"],
            api_key=doc["api_key"],
            whitelisted_ips=doc["whitelisted_ips"],
            tps_limit=doc["tps_limit"],
            status=doc.get("status", "active")
        )

class MongoClientUserRepository(ClientUserRepository):
    def __init__(self, db: Database):
        self.collection = db["client_users"]

    def get_by_user_id_and_client_id(self, user_id: str, client_id: str) -> Optional[ClientUser]:
        doc = self.collection.find_one({"user_id": user_id, "client_id": client_id, "status": "active"})
        if not doc:
            return None
        return ClientUser(
            user_id=doc["user_id"],
            client_id=doc["client_id"],
            name=doc["name"],
            status=doc.get("status", "active")
        )

class MongoAPILogRepository(APILogRepository):
    def __init__(self, db: Database):
        self.collection = db["api_logs"]
        # Ensure indexes for analytics performance
        self.collection.create_index([("client_id", ASCENDING)])
        self.collection.create_index([("timestamp", DESCENDING)])
        self.collection.create_index([("error_code", ASCENDING)])

    def save(self, log: APILog) -> None:
        self.collection.insert_one(log.to_dict())

    def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return list(self.collection.aggregate(pipeline))
