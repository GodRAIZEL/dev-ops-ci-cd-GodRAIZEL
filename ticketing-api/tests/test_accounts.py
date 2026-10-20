import pytest
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from tests.helpers import PASSWORD, assert_error

pytestmark = pytest.mark.django_db

REGISTER = "/api/auth/register/"
TOKEN = "/api/auth/token/"


def test_register_creates_standard_user_even_if_role_supplied(anon):
    payload = {"username": "alice", "email": "alice@example.com",
               "password": PASSWORD, "role": "admin"}
    response = anon.post(REGISTER, payload)
    assert response.status_code == 201
    assert "password" not in response.json()
    user = User.objects.get(username="alice")
    assert user.role == User.Role.USER
    assert user.check_password(PASSWORD)


def test_register_rejects_duplicate_email(anon, member):
    payload = {"username": "new", "email": member.email, "password": PASSWORD}
    error = assert_error(anon.post(REGISTER, payload), 400, "validation_error")
    assert "email" in error["details"]


@pytest.mark.parametrize("password", ["abc", "12345678", "password"])
def test_register_rejects_weak_passwords(anon, password):
    payload = {"username": "weak", "email": "weak@example.com", "password": password}
    error = assert_error(anon.post(REGISTER, payload), 400, "validation_error")
    assert "password" in error["details"]


def test_login_returns_tokens_with_role_claim_and_grants_access(anon, admin):
    response = anon.post(TOKEN, {"username": "admin", "password": PASSWORD})
    assert response.status_code == 200
    tokens = response.json()
    assert AccessToken(tokens["access"])["role"] == "admin"

    anon.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    me = anon.get("/api/auth/me/")
    assert me.status_code == 200
    assert me.json()["username"] == "admin"


def test_login_with_bad_credentials_uses_error_schema(anon, member):
    response = anon.post(TOKEN, {"username": "member", "password": "wrong"})
    assert_error(response, 401, "unauthorized")


def test_refresh_token_issues_new_access_token(anon, member):
    tokens = anon.post(TOKEN, {"username": "member", "password": PASSWORD}).json()
    response = anon.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]})
    assert response.status_code == 200
    assert "access" in response.json()


def test_me_requires_authentication(anon):
    assert_error(anon.get("/api/auth/me/"), 401, "unauthorized")


def test_me_rejects_garbage_token(anon):
    anon.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    assert_error(anon.get("/api/auth/me/"), 401, "unauthorized")


def test_is_admin_role(admin, member):
    superuser = User.objects.create_superuser("root", "root@example.com", PASSWORD)
    assert admin.is_admin_role
    assert superuser.is_admin_role
    assert not member.is_admin_role
