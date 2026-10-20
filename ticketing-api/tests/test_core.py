import json
from unittest import mock

import pytest
from django.db import IntegrityError, OperationalError
from django.db.models import ProtectedError

from core.exceptions import Conflict, custom_exception_handler
from core.views import not_found, server_error
from tests.helpers import assert_error

pytestmark = pytest.mark.django_db


def test_health_reports_database_uptime_and_status(anon):
    response = anon.get("/health/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "ticketing-api"
    assert body["database"]["connected"] is True
    assert body["uptime_seconds"] >= 0
    assert {"version", "timestamp"} <= set(body)


def test_health_returns_503_when_database_is_down(anon):
    with mock.patch("core.views.connection") as connection:
        connection.vendor = "postgresql"
        connection.cursor.side_effect = OperationalError("db down")
        response = anon.get("/health/")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"]["connected"] is False


def test_method_not_allowed_uses_error_schema(anon):
    assert_error(anon.post("/health/"), 405, "method_not_allowed")


def test_unknown_url_returns_json_404(client):
    assert_error(client.get("/definitely/not/here/"), 404, "not_found")


def test_json_404_and_500_handlers(rf):
    assert not_found(rf.get("/x/")).status_code == 404
    response = server_error(rf.get("/x/"))
    assert response.status_code == 500
    assert json.loads(response.content)["error"]["code"] == "server_error"


def test_exception_handler_maps_unexpected_and_database_errors():
    unexpected = custom_exception_handler(RuntimeError("boom"), {})
    assert unexpected.status_code == 500
    assert unexpected.data["error"]["code"] == "server_error"

    integrity = custom_exception_handler(IntegrityError("dup"), {})
    assert integrity.status_code == 409

    protected = custom_exception_handler(ProtectedError("in use", []), {})
    assert protected.status_code == 409


def test_conflict_exception_defaults():
    assert Conflict().status_code == 409


def test_openapi_schema_and_docs_are_served(anon):
    schema = anon.get("/api/schema/")
    assert schema.status_code == 200
    assert b"/api/bookings/" in schema.content
    assert b"/health/" in schema.content
    assert anon.get("/api/docs/").status_code == 200
    assert anon.get("/api/redoc/").status_code == 200
