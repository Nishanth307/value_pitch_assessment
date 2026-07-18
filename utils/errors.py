import uuid
from flask import jsonify, g

# Mapping error codes to (HTTP status code, default error message)
ERROR_CODES = {
    "VP2000": (200, "Verified via primary vendor"),
    "VP2001": (200, "Verified via fallback vendor"),
    "VP2002": (200, "Processed, but record not verified (not found / name mismatch)"),
    "VP4001": (401, "Missing or invalid API key"),
    "VP4003": (403, "Source IP not whitelisted"),
    "VP4022": (422, "Request payload validation failed"),
    "VP4029": (429, "Client TPS limit exceeded"),
    "VP5001": (502, "Primary vendor failed AND fallback failed"),
    "VP5000": (500, "Unhandled internal error")
}

def get_error_info(error_code):
    """Retrieve the HTTP status code and default message for a given error code."""
    return ERROR_CODES.get(error_code, (500, "Unhandled internal error"))

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
    """Register custom error handlers on the Flask app to return clean JSON envelopes."""
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
