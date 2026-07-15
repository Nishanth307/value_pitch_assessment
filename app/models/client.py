from app.extensions import mongo

class Client:
    """Class representation of a Client document in MongoDB."""
    def __init__(self, client_id: str, name: str, api_key: str, whitelisted_ips: list, tps_limit: int, status: str = "active"):
        self.client_id = client_id
        self.name = name
        self.api_key = api_key
        self.whitelisted_ips = whitelisted_ips
        self.tps_limit = tps_limit
        self.status = status

    def to_dict(self) -> dict:
        return {
            "client_id": self.client_id,
            "name": self.name,
            "api_key": self.api_key,
            "whitelisted_ips": self.whitelisted_ips,
            "tps_limit": self.tps_limit,
            "status": self.status
        }

    @classmethod
    def find_by_api_key(cls, api_key: str) -> dict | None:
        """Find a client in MongoDB by their API key."""
        if not api_key:
            return None
        return mongo.db.clients.find_one({"api_key": api_key})
