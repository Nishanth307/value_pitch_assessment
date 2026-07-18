import hashlib
from functools import wraps
from flask import request, g
import models
from utils.errors import AuthError, ValidationError, IpNotWhitelistedError

def mask_id_number(id_number: str) -> str:
    """Mask all but the last 4 characters of an ID number with asterisks."""
    if not id_number:
        return ""
    id_str = str(id_number).strip()
    length = len(id_str)
    if length <= 4:
        return "*" * (length - 1) + id_str[-1:] if length > 0 else ""
    return "*" * (length - 4) + id_str[-4:]

def mask_name(name: str) -> str:
    """Mask name by revealing only the first character of each word."""
    if not name:
        return ""
    name_str = str(name).strip()
    words = name_str.split()
    masked_words = [w[0] + "*" * (len(w) - 1) if len(w) > 1 else w for w in words]
    return " ".join(masked_words)

def hash_value(value: str) -> str:
    """Generate a SHA-256 hex digest of a string value."""
    if value is None:
        return ""
    val_bytes = str(value).strip().encode("utf-8")
    return hashlib.sha256(val_bytes).hexdigest()

def get_client_ip() -> str:
    """Resolve the client's IP address, checking X-Forwarded-For (for proxies/K8s) first."""
    x_forwarded = request.headers.get("X-Forwarded-For")
    if x_forwarded:
        # X-Forwarded-For can be a comma-separated list of IPs. The client IP is the first one.
        parts = [ip.strip() for ip in x_forwarded.split(",")]
        if parts:
            return parts[0]
    return request.remote_addr

def require_client_auth(f):
    """Decorator to authenticate client API key and check sub-user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            raise AuthError("Missing X-API-Key header")
            
        client = models.Client.find_by_api_key(api_key)
        if not client:
            raise AuthError("Invalid or inactive API key")
            
        g.client = client
        g.client_id = client.get("client_id")
        
        user_id = request.headers.get("X-User-Id")
        if not user_id:
            raise ValidationError("Missing X-User-Id header")
            
        # Verify sub-user belongs to this client
        user = models.ClientUser.find_user(g.client_id, user_id)
        if not user:
            raise ValidationError(f"Invalid or inactive sub-user: '{user_id}'")
            
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated

def require_ip_whitelist(f):
    """Decorator to verify the client IP address is whitelisted for the authenticated client."""
    @wraps(f)
    def decorated(*args, **kwargs):
        client_ip = get_client_ip()
        g.client_ip = client_ip
        
        client = getattr(g, "client", None)
        if not client:
            raise IpNotWhitelistedError("IP check failed due to missing client auth context")
            
        whitelisted_ips = client.get("whitelisted_ips", [])
        if client_ip not in whitelisted_ips:
            raise IpNotWhitelistedError(f"Client IP '{client_ip}' is not whitelisted")
            
        return f(*args, **kwargs)
    return decorated
