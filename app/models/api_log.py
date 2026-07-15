from app.extensions import mongo

class ApiLog:
    """Class representing transaction log schema helper and aggregator."""
    @classmethod
    def insert_log(cls, log_doc: dict) -> None:
        """Insert a verification request API log into MongoDB."""
        mongo.db.api_logs.insert_one(log_doc)

    @classmethod
    def run_aggregation(cls, pipeline: list) -> list:
        """Run a MongoDB aggregation pipeline on the api_logs collection."""
        return list(mongo.db.api_logs.aggregate(pipeline))

    @classmethod
    def count_logs(cls, filter_stage: dict) -> int:
        """Count logs matching a filter query."""
        return mongo.db.api_logs.count_documents(filter_stage)
