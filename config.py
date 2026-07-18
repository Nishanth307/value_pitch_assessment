import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    """Application configuration loaded from environment variables."""
    # MongoDB Config
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "verigate")

    # API Keys
    ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "admin_secret_key_123")

    # Vendor Simulation Settings
    # Vendor A (Primary) can simulate failure rate and timeout rate (between 0.0 and 1.0)
    VENDOR_A_FAILURE_RATE = float(os.environ.get("VENDOR_A_FAILURE_RATE", 0.1))
    VENDOR_A_TIMEOUT_RATE = float(os.environ.get("VENDOR_A_TIMEOUT_RATE", 0.1))
    VENDOR_MIN_LATENCY_MS = int(os.environ.get("VENDOR_MIN_LATENCY_MS", 100))
    VENDOR_MAX_LATENCY_MS = int(os.environ.get("VENDOR_MAX_LATENCY_MS", 1000))
    VENDOR_TIMEOUT_BUDGET_MS = int(os.environ.get("VENDOR_TIMEOUT_BUDGET_MS", 500))

    # General Flask settings
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    TESTING = False

class TestingConfig(Config):
    """Testing-specific configuration."""
    TESTING = True
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME_TEST", "verigate_test")
