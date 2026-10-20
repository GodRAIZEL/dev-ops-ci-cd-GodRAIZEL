PASSWORD = "Str0ng-Passw0rd!x"


def assert_error(response, status_code, code=None):
    """Assert the standardised error schema and return the error object."""
    assert response.status_code == status_code
    error = response.json()["error"]
    assert {"code", "message", "status"} <= set(error)
    assert error["status"] == status_code
    if code:
        assert error["code"] == code
    return error
