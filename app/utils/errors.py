import uuid
from flask import jsonify, g
from app.utils.error_codes import get_error_info

class AppError(Exception):
    """Base exception class for VeriGate custom errors."""
    def __init__(self, error_code, message=None, http_status=None, extra=None):
        default_status, default_msg = get_error_info(error_code)
        self.error_code = error_code
        self.message = message if message is not None else default_msg
        self.http_status = http_status if http_status is not None else default_status
        self.extra = extra or {}
        super().__init__(self.message)

class AuthError(AppError):
    """Raised when API key is missing or invalid."""
    def __init__(self, message=None, extra=None):
        super().__init__("VP4001", message=message, extra=extra)

class IpNotWhitelistedError(AppError):
    """Raised when client's IP is not in their whitelisted_ips array."""
    def __init__(self, message=None, extra=None):
        super().__init__("VP4003", message=message, extra=extra)

class ValidationError(AppError):
    """Raised when request payload verification fails."""
    def __init__(self, message=None, extra=None):
        super().__init__("VP4022", message=message, extra=extra)

class TpsLimitError(AppError):
    """Raised when client exceeds their assigned Transactions Per Second limit."""
    def __init__(self, message=None, extra=None):
        super().__init__("VP4029", message=message, extra=extra)

class VendorFailureError(AppError):
    """Raised when primary vendor fails and fallback also fails."""
    def __init__(self, message=None, extra=None):
        super().__init__("VP5001", message=message, extra=extra)

def get_request_id():
    """Ensure a request_id is always available on flask.g."""
    if not hasattr(g, "request_id") or not g.request_id:
        g.request_id = f"req_{uuid.uuid4().hex[:8]}"
    return g.request_id

def register_error_handlers(app):
    """Register custom error handlers on the Flask app."""
    @app.errorhandler(AppError)
    def handle_app_error(err):
        req_id = get_request_id()
        response = {
            "request_id": req_id,
            "status": "FAILED",
            "error_code": err.error_code,
            "message": err.message
        }
        return jsonify(response), err.http_status

    @app.errorhandler(Exception)
    def handle_generic_exception(err):
        app.logger.error(f"Unhandled exception: {str(err)}", exc_info=True)
        req_id = get_request_id()
        response = {
            "request_id": req_id,
            "status": "FAILED",
            "error_code": "VP5000",
            "message": "Unhandled internal error"
        }
        return jsonify(response), 500
