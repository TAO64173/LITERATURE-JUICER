"""卡密数据库模块测试"""

import sqlite3
import pytest


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """每个测试使用独立的临时数据库，自动清理"""
    import backend.db_manager as db

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    return db_path


def _insert_code(db_path, code: str, total: int, used: int = 0):
    """辅助：直接插入卡密"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO codes_table (code, total_quota, used_quota) VALUES (?, ?, ?)",
        (code, total, used),
    )
    conn.commit()
    conn.close()


class TestInitDb:
    def test_table_exists_after_init(self, test_db):
        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='codes_table'"
        ).fetchone()
        conn.close()
        assert row is not None

    def test_init_is_idempotent(self, test_db):
        from backend.db_manager import init_db

        init_db()
        init_db()


class TestValidateCode:
    def test_valid_code_returns_true(self, test_db):
        from backend.db_manager import validate_code

        _insert_code(test_db, "TEST123", 10)
        assert validate_code("TEST123") is True

    def test_invalid_code_returns_false(self, test_db):
        from backend.db_manager import validate_code

        assert validate_code("NOTEXIST") is False


class TestInsertAndQuery:
    def test_insert_and_check_remaining(self, test_db):
        from backend.db_manager import get_remaining_quota

        _insert_code(test_db, "TEST123", 10)
        assert get_remaining_quota("TEST123") == 10

    def test_nonexistent_code_returns_none(self, test_db):
        from backend.db_manager import get_remaining_quota

        assert get_remaining_quota("NOTEXIST") is None


class TestDeductQuota:
    def test_deduct_success(self, test_db):
        from backend.db_manager import deduct_quota, get_remaining_quota

        _insert_code(test_db, "TEST123", 10)
        assert deduct_quota("TEST123", 3) is True
        assert get_remaining_quota("TEST123") == 7

    def test_deduct_exact_balance(self, test_db):
        from backend.db_manager import deduct_quota, get_remaining_quota

        _insert_code(test_db, "TEST123", 5)
        assert deduct_quota("TEST123", 5) is True
        assert get_remaining_quota("TEST123") == 0

    def test_deduct_insufficient_balance(self, test_db):
        from backend.db_manager import deduct_quota, get_remaining_quota

        _insert_code(test_db, "TEST123", 3)
        assert deduct_quota("TEST123", 5) is False
        assert get_remaining_quota("TEST123") == 3

    def test_deduct_invalid_code(self, test_db):
        from backend.db_manager import deduct_quota

        assert deduct_quota("NOTEXIST", 1) is False

    def test_multiple_deducts(self, test_db):
        from backend.db_manager import deduct_quota, get_remaining_quota

        _insert_code(test_db, "TEST123", 10)
        deduct_quota("TEST123", 2)
        deduct_quota("TEST123", 3)
        assert get_remaining_quota("TEST123") == 5
