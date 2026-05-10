"""卡密验证接口测试"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sqlite3

from backend.main import app
from backend import db_manager


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """使用临时数据库，禁用缓存和速率限制"""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_manager, "DB_PATH", db_path)
    # 禁用 Redis 缓存
    monkeypatch.setattr("backend.cache._cache_enabled", False)
    # 禁用速率限制（测试中不应被限流干扰）
    monkeypatch.setattr("backend.api.code_api.rate_limit_check", lambda ip, code: (False, ""))
    db_manager.init_db()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO codes_table (code, total_quota, used_quota) VALUES (?, ?, ?)",
        ("TEST123", 20, 5),
    )
    conn.commit()
    conn.close()


client = TestClient(app)


class TestValidateCode:
    def test_valid_code_deducts_and_returns_remaining(self):
        resp = client.post("/validate-code", json={"code": "TEST123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "验证成功"
        # 20 - 5 = 15, 扣减后 = 14
        assert data["remaining_quota"] == 14

    def test_invalid_code(self):
        resp = client.post("/validate-code", json={"code": "NOTEXIST"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["message"] == "卡密无效或额度不足"

    def test_empty_code(self):
        resp = client.post("/validate-code", json={"code": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    def test_missing_code_field(self):
        resp = client.post("/validate-code", json={})
        assert resp.status_code == 422

    def test_multiple_validations_deduct_sequentially(self):
        """连续验证应逐次扣减"""
        r1 = client.post("/validate-code", json={"code": "TEST123"})
        assert r1.json()["remaining_quota"] == 14

        r2 = client.post("/validate-code", json={"code": "TEST123"})
        assert r2.json()["remaining_quota"] == 13

    def test_exhausted_quota_returns_fail(self):
        """额度用完后应返回失败"""
        # 先用完额度（初始 15）
        for _ in range(15):
            client.post("/validate-code", json={"code": "TEST123"})

        resp = client.post("/validate-code", json={"code": "TEST123"})
        data = resp.json()
        assert data["success"] is False
        assert data["remaining_quota"] == 0
