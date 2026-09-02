import pytest

from app.core.deps import assert_allowed_role, role_has_scope
from app.core.errors import AppError


def test_assert_allowed_role_allows_matching_role():
    assert_allowed_role("AGENT", ("AGENT", "MANAGER", "ADMIN"))  # must not raise


def test_assert_allowed_role_denies_wrong_role():
    with pytest.raises(AppError) as exc:
        assert_allowed_role("AGENT", ("ADMIN",))
    assert exc.value.status_code == 403
    assert exc.value.error_code == "ACCESS_DENIED"


def test_role_scope_feature_matrix():
    # ticket scope
    assert role_has_scope("AGENT", "tickets")
    assert role_has_scope("MANAGER", "tickets")
    assert role_has_scope("ADMIN", "tickets")
    # dashboard scope (S5)
    assert not role_has_scope("AGENT", "dashboard")
    assert role_has_scope("MANAGER", "dashboard")
    assert role_has_scope("ADMIN", "dashboard")
    # admin scope (S6)
    assert not role_has_scope("AGENT", "admin")
    assert not role_has_scope("MANAGER", "admin")
    assert role_has_scope("ADMIN", "admin")
    # unknown feature is always denied
    assert not role_has_scope("ADMIN", "unknown_feature")
