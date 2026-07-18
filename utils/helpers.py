from datetime import datetime
from functools import wraps
from flask import request, g
from utils.errors import ValidationError

def validate_verify_payload(f):
    """Decorator to validate verification request JSON payloads."""
    @wraps(f)
    def decorated(*args, **kwargs):
        payload = request.get_json(silent=True)
        if not payload:
            raise ValidationError("Request body must be valid JSON")
            
        client_ref_id = payload.get("client_ref_id")
        if not client_ref_id or not isinstance(client_ref_id, str) or not client_ref_id.strip():
            raise ValidationError("Field 'client_ref_id' is required and must be a non-empty string")
            
        id_type = payload.get("id_type")
        allowed_types = {"PAN", "DL", "VOTER"}
        if not id_type or id_type not in allowed_types:
            raise ValidationError(f"Field 'id_type' must be one of: {', '.join(allowed_types)}")
            
        id_number = payload.get("id_number")
        if not id_number or not isinstance(id_number, str) or not id_number.strip():
            raise ValidationError("Field 'id_number' is required and must be a non-empty string")
            
        name = payload.get("name")
        if not name or not isinstance(name, str) or not name.strip():
            raise ValidationError("Field 'name' is required and must be a non-empty string")
            
        # Strip fields and store them in Flask global 'g' context for access in route handlers
        g.client_ref_id = client_ref_id.strip()
        g.id_type = id_type
        g.id_number = id_number.strip()
        g.name = name.strip()
        
        return f(*args, **kwargs)
    return decorated

def parse_iso_date(date_str: str, field_name: str) -> datetime:
    """Safely parses an ISO-8601 date string to a datetime object."""
    if not date_str:
        raise ValidationError(f"Query parameter '{field_name}' is required")
    try:
        # Handles Zulu (Z) timezone notation
        clean_str = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except ValueError:
        raise ValidationError(f"Parameter '{field_name}' must be a valid ISO-8601 date string (e.g. YYYY-MM-DDTHH:MM:SSZ)")
