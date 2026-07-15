import pytest
from app import create_app
from app.config import TestingConfig
from app.extensions import mongo
from app.services import vendors as orchestrator
from app.services import rate_limiter as tps_limiter

@pytest.fixture
def app():
    # Use the isolated testing configuration
    app = create_app(TestingConfig)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture(autouse=True)
def cleanup_and_reset(app):
    """Reset MongoDB, circuit breaker, and TPS rate limiters before each test."""
    with app.app_context():
        # Clear collections
        mongo.db.clients.drop()
        mongo.db.client_users.drop()
        mongo.db.api_logs.drop()
        
        # Seed test data
        mongo.db.clients.insert_one({
            "client_id": "test_client",
            "name": "Test Client",
            "api_key": "test_api_key_123",
            "whitelisted_ips": ["127.0.0.1", "192.168.1.5"],
            "tps_limit": 2,
            "status": "active"
        })
        
        mongo.db.client_users.insert_one({
            "user_id": "test_user_01",
            "client_id": "test_client",
            "name": "Test User One",
            "status": "active"
        })
        
    # Reset circuit breaker state
    orchestrator._failure_timestamps.clear()
    orchestrator._circuit_open_until = 0.0
    
    # Reset TPS rate limiter state
    tps_limiter._limiter_store.clear()
    
    yield
    
    with app.app_context():
        mongo.db.clients.drop()
        mongo.db.client_users.drop()
        mongo.db.api_logs.drop()
