from flask import current_app

class Client:
    """Helper representing a Client document in MongoDB."""
    @classmethod
    def get_collection(cls):
        return current_app.db.clients

    @classmethod
    def find_by_api_key(cls, api_key: str) -> dict:
        """Find a client by their API key."""
        if not api_key:
            return None
        return cls.get_collection().find_one({"api_key": api_key, "status": "active"})

    @classmethod
    def find_by_client_id(cls, client_id: str) -> dict:
        """Find a client by their client_id."""
        if not client_id:
            return None
        return cls.get_collection().find_one({"client_id": client_id, "status": "active"})


class ClientUser:
    """Helper representing a Client's sub-user document in MongoDB."""
    @classmethod
    def get_collection(cls):
        return current_app.db.client_users

    @classmethod
    def find_user(cls, client_id: str, user_id: str) -> dict:
        """Find an active sub-user associated with a client."""
        if not client_id or not user_id:
            return None
        return cls.get_collection().find_one({
            "client_id": client_id,
            "user_id": user_id,
            "status": "active"
        })


class ApiLog:
    """Helper representing transaction log collection helper and aggregator."""
    @classmethod
    def get_collection(cls):
        return current_app.db.api_logs

    @classmethod
    def insert_log(cls, log_doc: dict) -> None:
        """Insert a verification request API log into MongoDB."""
        cls.get_collection().insert_one(log_doc)

    @classmethod
    def run_aggregation(cls, pipeline: list) -> list:
        """Run a MongoDB aggregation pipeline on the api_logs collection."""
        return list(cls.get_collection().aggregate(pipeline))

    @classmethod
    def count_logs(cls, filter_query: dict) -> int:
        """Count logs matching a filter query."""
        return cls.get_collection().count_documents(filter_query)
