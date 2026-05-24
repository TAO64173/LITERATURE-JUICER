"""Tests for invite API endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.api import invite_api
from backend.main import app

client = TestClient(app)


class TestInviteInfo:
    def test_returns_invite_code_and_count(self):
        resp = client.get("/invite/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["invite_code"] == "TEST1"
        assert data["invited_count"] == 0

    def test_returns_real_count_when_invited(self, monkeypatch):
        monkeypatch.setattr(
            invite_api, "get_invite_info",
            lambda uid, email: {"invite_code": "ABC12", "invited_count": 3},
        )
        resp = client.get("/invite/info")
        data = resp.json()
        assert data["invited_count"] == 3
        assert data["invite_code"] == "ABC12"


class TestApplyInvite:
    def test_apply_invite_success(self):
        resp = client.post("/invite/apply", json={"code": "ABC12"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "邀请码使用成功" in data["message"]

    def test_apply_invite_invalid_code(self, monkeypatch):
        monkeypatch.setattr(
            invite_api, "apply_invite_code",
            lambda uid, email, code: {"success": False, "message": "邀请码格式无效"},
        )
        resp = client.post("/invite/apply", json={"code": "AB"})
        data = resp.json()
        assert data["success"] is False

    def test_apply_invite_self_invite(self, monkeypatch):
        monkeypatch.setattr(
            invite_api, "apply_invite_code",
            lambda uid, email, code: {"success": False, "message": "不能使用自己的邀请码"},
        )
        resp = client.post("/invite/apply", json={"code": "SELF1"})
        data = resp.json()
        assert data["success"] is False
        assert "自己" in data["message"]

    def test_apply_invite_already_used(self, monkeypatch):
        monkeypatch.setattr(
            invite_api, "apply_invite_code",
            lambda uid, email, code: {"success": False, "message": "你已经使用过邀请码了"},
        )
        resp = client.post("/invite/apply", json={"code": "USED1"})
        data = resp.json()
        assert data["success"] is False
        assert "已经" in data["message"]

    def test_apply_invite_nonexistent_code(self, monkeypatch):
        monkeypatch.setattr(
            invite_api, "apply_invite_code",
            lambda uid, email, code: {"success": False, "message": "邀请码不存在"},
        )
        resp = client.post("/invite/apply", json={"code": "XXXXX"})
        data = resp.json()
        assert data["success"] is False
        assert "不存在" in data["message"]
