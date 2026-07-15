import uuid
from flask import Flask, g
from .config import Config
from .extensions import mongo
from .interfaces.verify_routes import verify_bp
from .interfaces.mis_routes import mis_bp
from .services.container import Container
from .utils.errors import register_error_handlers

def create_app(config_object=None):
    app = Flask(__name__)
    
    if config_object:
        app.config.from_object(config_object)
    else:
        app.config.from_object(Config)
        
    # Initialize Extensions
    mongo.init_app(app)
    
    # Initialize Dependency Injection Container
    with app.app_context():
        app.container = Container(app.config)
    
    # Generate request ID on each request
    @app.before_request
    def setup_request():
        g.request_id = f"req_{uuid.uuid4().hex[:8]}"
        
    # Register Blueprints
    app.register_blueprint(verify_bp)
    app.register_blueprint(mis_bp)
    
    # Register Error Handlers
    register_error_handlers(app)
    
    return app
