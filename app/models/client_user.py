from app.extensions import mongo

class ClientUser:
    """Class representation of a Client's sub-user document in MongoDB."""
    def __init__(self, user_id: str, client_id: str, name: str, status: str = "active"):
        self.user_id = user_id
        self.client_id = client_id
        self.name = name
        self.status = status

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "client_id": self.client_id,
            "name": self.name,
            "status": self.status
        }

    @classmethod
    def find_user(cls, client_id: str, user_id: str) -> dict | None:
        """Find a specific sub-user associated with a client."""
        if not client_id or not user_id:
            return None
        return mongo.db.client_users.find_one({"client_id": client_id, "user_id": user_id})
