import pytest
from utils.security import mask_id_number, mask_name, hash_value
from utils.errors import (
    AppError, AuthError, IpNotWhitelistedError,
    ValidationError, TpsLimitError, VendorFailureError
)

def test_pii_masking():
    # ID number masking
    assert mask_id_number("1234567890") == "******7890"
    assert mask_id_number("12345") == "*2345"
    assert mask_id_number("123") == "**3"
    assert mask_id_number("") == ""
    assert mask_id_number(None) == ""

    # Name masking
    assert mask_name("John Doe") == "J*** D**"
    assert mask_name("Alice") == "A****"
    assert mask_name("A B C") == "A B C"
    assert mask_name("  John   Doe  ") == "J*** D**"
    assert mask_name("") == ""
    assert mask_name(None) == ""

    # Hash value
    assert hash_value("my_secret_id") == "4dcef4879025cdd7a84ed35330695e576cf541fc23b3c00d6cc5709ea1b5003e"
    assert hash_value("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" # SHA-256 for empty string
    assert hash_value(None) == ""

def test_custom_exceptions():
    # AuthError (VP4001)
    err = AuthError()
    assert err.error_code == "VP4001"
    assert err.http_status == 401
    assert "API key" in err.message

    # Custom message AuthError
    err = AuthError(message="Custom key error")
    assert err.message == "Custom key error"

    # IpNotWhitelistedError (VP4003)
    err = IpNotWhitelistedError()
    assert err.error_code == "VP4003"
    assert err.http_status == 403
    assert "IP" in err.message

    # ValidationError (VP4022)
    err = ValidationError()
    assert err.error_code == "VP4022"
    assert err.http_status == 422

    # TpsLimitError (VP4029)
    err = TpsLimitError()
    assert err.error_code == "VP4029"
    assert err.http_status == 429

    # VendorFailureError (VP5001)
    err = VendorFailureError()
    assert err.error_code == "VP5001"
    assert err.http_status == 502
