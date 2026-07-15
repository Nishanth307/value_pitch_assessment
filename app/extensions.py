from pymongo import MongoClient

class PyMongoExtension:
    def __init__(self):
        self.client = None
        self.db = None

    def init_app(self, app):
        mongo_uri = app.config.get("MONGO_URI", "mongodb://localhost:27017/")
        db_name = app.config.get("MONGO_DB_NAME", "verigate")
        # Ensure we connect to the MongoDB client
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]

# Singleton instance of our PyMongo wrapper
mongo = PyMongoExtension()
