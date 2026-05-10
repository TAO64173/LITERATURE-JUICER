"""
SQLite 卡密管理模块
自动创建数据库和表结构，提供卡密验证、扣费、查询功能
"""

import sqlite3
from pathlib import Path

# 数据库文件路径（项目根目录下的 database.db）
DB_PATH = Path(__file__).parent.parent / "database.db"


def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库，创建 codes_table（如不存在）"""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS codes_table (
                code TEXT PRIMARY KEY,
                total_quota INTEGER NOT NULL,
                used_quota INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


def validate_code(code: str) -> bool:
    """验证卡密是否存在"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM codes_table WHERE code = ?", (code,)
        ).fetchone()
        return row is not None


def deduct_quota(code: str, amount: int = 1) -> bool:
    """
    扣除卡密配额
    返回 True 扣费成功，False 余额不足或卡密无效
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT total_quota, used_quota FROM codes_table WHERE code = ?",
            (code,),
        ).fetchone()
        if row is None:
            return False
        if row["total_quota"] - row["used_quota"] < amount:
            return False
        conn.execute(
            "UPDATE codes_table SET used_quota = used_quota + ? WHERE code = ?",
            (amount, code),
        )
        conn.commit()
        return True


def get_remaining_quota(code: str) -> int | None:
    """
    查询卡密剩余配额
    返回剩余次数，卡密无效返回 None
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT total_quota, used_quota FROM codes_table WHERE code = ?",
            (code,),
        ).fetchone()
        if row is None:
            return None
        return row["total_quota"] - row["used_quota"]


def get_next_beta_code() -> str | None:
    """获取下一个有剩余额度的 BETA 卡密，按编号顺序返回"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT code FROM codes_table WHERE code LIKE 'BETA%' AND total_quota > used_quota ORDER BY code LIMIT 1"
        ).fetchone()
        return row["code"] if row else None


# === 独立测试 ===
if __name__ == "__main__":
    import os

    # 使用临时数据库测试
    DB_PATH = Path(__file__).parent.parent / "test_database.db"

    init_db()
    print("[OK] 数据库初始化完成")

    # 插入测试卡密
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO codes_table (code, total_quota, used_quota) VALUES (?, ?, ?)",
            ("TEST-CODE-001", 10, 0),
        )
        conn.commit()

    # 测试验证
    assert validate_code("TEST-CODE-001") is True
    assert validate_code("INVALID-CODE") is False
    print("[OK] 卡密验证通过")

    # 测试查询余额
    assert get_remaining_quota("TEST-CODE-001") == 10
    assert get_remaining_quota("INVALID-CODE") is None
    print("[OK] 余额查询通过")

    # 测试扣费
    assert deduct_quota("TEST-CODE-001", 3) is True
    assert get_remaining_quota("TEST-CODE-001") == 7
    assert deduct_quota("TEST-CODE-001", 8) is False  # 余额不足
    assert get_remaining_quota("TEST-CODE-001") == 7  # 未变化
    print("[OK] 扣费逻辑通过")

    # 清理测试数据库
    try:
        os.remove(DB_PATH)
        print("[OK] 已清理测试数据库")
    except PermissionError:
        print("[跳过] 测试数据库被占用，可手动删除 test_database.db")
    print("[OK] 全部测试通过")
