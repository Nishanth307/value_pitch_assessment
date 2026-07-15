# Central source of truth mapping app error codes to (http_status, default_message)

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
