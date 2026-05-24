"""额度查询接口测试"""

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


class TestQuota:
    def test_get_quota_success(self):
        """已认证用户可获取额度信息"""
        resp = client.get("/quota")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total"] == 3
        assert data["used"] == 0
        assert data["remaining"] == 3

    def test_get_quota_response_shape(self):
        """响应包含所需字段（含 role）"""
        resp = client.get("/quota")
        data = resp.json()
        assert "total" in data
        assert "used" in data
        assert "remaining" in data
        assert "role" in data
        assert isinstance(data["total"], int)
        assert isinstance(data["used"], int)
        assert isinstance(data["remaining"], int)
        assert data["role"] in ("admin", "user")

    def test_default_role_is_user(self):
        """普通用户 role 为 user"""
        resp = client.get("/quota")
        data = resp.json()
        assert data["role"] == "user"
