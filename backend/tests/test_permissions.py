import pytest
from fastapi import HTTPException

from app.core.permissions import require_roles
from app.models.user import User


@pytest.mark.parametrize(
    "role",
    ["admin", "manager", "operator", "viewer"],
)
def test_valid_roles_are_accepted(role):
    user = User(
        id=1,
        username="testuser",
        password_hash="test-hash",
        role=role,
        active=True,
    )

    assert require_roles(role)(user) is user


def test_disallowed_role_is_forbidden():
    user = User(
        id=1,
        username="operator1",
        password_hash="test-hash",
        role="operator",
        active=True,
    )

    checker = require_roles("admin")

    with pytest.raises(HTTPException) as exc:
        checker(user)

    assert exc.value.status_code == 403


def test_invalid_role_configuration_is_rejected():
    with pytest.raises(ValueError):
        require_roles("superuser")


def test_empty_role_configuration_is_rejected():
    with pytest.raises(ValueError):
        require_roles()
