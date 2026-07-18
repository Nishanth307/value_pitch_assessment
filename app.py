import os
import uuid
from flask import Flask, g
from pymongo import MongoClient
from config import Config

# Global database client and database object
db_client = None
db = None

def create_app(config_class=Config):
    """Flask Application Factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    global db_client, db
    # Initialize MongoDB Client
    db_client = MongoClient(app.config["MONGO_URI"])
    db = db_client[app.config["MONGO_DB_NAME"]]
    # Attach to app object for easy access across the application
    app.db = db

    # Setup unique Request ID for each request for tracking and auditing
    @app.before_request
    def setup_request_id():
        g.request_id = f"req_{uuid.uuid4().hex[:8]}"

    # Error Handlers registration (we will implement error handling helper next)
    from utils.errors import register_error_handlers
    register_error_handlers(app)

    # Blueprint Registration
    from routes.verify import verify_bp
    from routes.mis import mis_bp
    app.register_blueprint(verify_bp)
    app.register_blueprint(mis_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
