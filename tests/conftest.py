"""Shared test fixtures for auth and Supabase mocking."""

import pytest
from unittest.mock import patch

from backend.main import app
from backend.auth import verify_clerk_token
from backend.api import upload_api
from backend.api import invite_api


MOCK_TOKEN_PAYLOAD = {
    "sub": "user_test123",
    "email": "test@example.com",
}


def _override_verify_clerk_token():
    return MOCK_TOKEN_PAYLOAD


@pytest.fixture(autouse=True)
def mock_auth():
    """Override Clerk JWT verification for all tests."""
    app.dependency_overrides[verify_clerk_token] = _override_verify_clerk_token
    yield
    app.dependency_overrides.pop(verify_clerk_token, None)


@pytest.fixture(autouse=True)
def mock_supabase(monkeypatch):
    """Mock all Supabase operations for all tests."""
    monkeypatch.setattr(
        upload_api, "ensure_user_and_quota",
        lambda uid, email: {"total_quota": 3, "used_quota": 0, "role": "user"},
    )
    monkeypatch.setattr(
        upload_api, "get_remaining_quota",
        lambda uid, email="": 3,
    )
    monkeypatch.setattr(
        upload_api, "deduct_quota_batch",
        lambda uid, count, email="": (True, 3 - count),
    )
    monkeypatch.setattr(
        upload_api, "get_user_role",
        lambda email: "user",
    )
    # Invite API mocks
    monkeypatch.setattr(
        invite_api, "ensure_user_and_quota",
        lambda uid, email: {"total_quota": 3, "used_quota": 0, "role": "user"},
    )
    monkeypatch.setattr(
        invite_api, "get_invite_info",
        lambda uid, email: {"invite_code": "TEST1", "invited_count": 0},
    )
    monkeypatch.setattr(
        invite_api, "generate_user_invite_code",
        lambda uid, email: "TEST1",
    )
    monkeypatch.setattr(
        invite_api, "apply_invite_code",
        lambda uid, email, code: {"success": True, "message": "邀请码使用成功！邀请人已获得 2 篇额度"},
    )

