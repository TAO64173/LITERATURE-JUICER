"""卡密验证接口测试"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sqlite3

from backend.main import app
from backend import db_manager


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """使用临时数据库"""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_manager, "DB_PATH", db_path)
    db_manager.init_db()
    # 插入测试卡密
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO codes_table (code, total_quota, used_quota) VALUES (?, ?, ?)",
        ("TEST123", 20, 5),
    )
    conn.commit()
    conn.close()


client = TestClient(app)


class TestValidateCode:
    def test_valid_code(self):
        resp = client.post("/validate-code", json={"code": "TEST123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "验证成功"
        assert data["remaining_quota"] == 15

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
