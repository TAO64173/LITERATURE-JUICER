"""
SQLite 卡密管理模块
自动创建数据库和表结构，提供卡密验证、扣费、查询功能
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# 数据库文件路径（项目根目录下的 database.db）
DB_PATH = Path(__file__).parent.parent / "database.db"

# 默认配额（每个卡密）
DEFAULT_QUOTA = 3


def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _seed_beta_codes(conn: sqlite3.Connection) -> int:
    """从 beta_codes.txt 读取卡密并插入数据库，返回新插入数量"""
    codes_file = Path(__file__).parent.parent / "beta_codes.txt"
    if not codes_file.exists():
        logger.info("beta_codes.txt 不存在，跳过 seed")
        return 0

    codes = [line.strip() for line in codes_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not codes:
        logger.info("beta_codes.txt 为空，跳过 seed")
        return 0

    inserted = 0
    for code in codes:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO codes_table (code, total_quota, used_quota) VALUES (?, ?, 0)",
                (code, DEFAULT_QUOTA),
            )
            inserted += 1
        except sqlite3.Error as e:
            logger.warning(f"插入卡密 {code} 失败: {e}")

    conn.commit()
    return inserted


def init_db():
    """初始化数据库，创建 codes_table（如不存在），并自动 seed 卡密"""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS codes_table (
                code TEXT PRIMARY KEY,
                total_quota INTEGER NOT NULL,
                used_quota INTEGER NOT NULL DEFAULT 0
            )
        """)

        # 检查表是否为空，为空则自动 seed
        count = conn.execute("SELECT COUNT(*) FROM codes_table").fetchone()[0]
        logger.info(f"数据库路径: {DB_PATH}")
        if count == 0:
            seeded = _seed_beta_codes(conn)
            logger.info(f"数据库为空，已自动导入 {seeded} 个卡密")
        else:
            logger.info(f"数据库已有 {count} 条卡密记录")


def validate_code(code: str) -> bool:
    """验证卡密是否存在"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM codes_table WHERE code = ?", (code,)
        ).fetchone()
        return row is not None


def deduct_quota(code: str, amount: int = 1) -> bool:
    """
    原子扣除卡密配额
    使用单条 SQL 完成检查+扣减，避免并发竞争
    返回 True 扣费成功，False 余额不足或卡密无效
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE codes_table SET used_quota = used_quota + ? "
            "WHERE code = ? AND (total_quota - used_quota) >= ?",
            (amount, code, amount),
        )
        conn.commit()
        return cursor.rowcount > 0


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


def validate_and_deduct(code: str) -> tuple[bool, int | None, str]:
    """
    验证卡密并原子扣减 1 次配额
    返回 (success, remaining_quota, message)
    """
    from backend.cache import get_cached_quota, set_cached_quota, invalidate_code

    # 负缓存：已知无效的卡密直接返回
    cached = get_cached_quota(code)
    if cached is not None and cached <= 0:
        return False, 0, "卡密无效或额度不足"

    with get_connection() as conn:
        row = conn.execute(
            "SELECT total_quota, used_quota FROM codes_table WHERE code = ?",
            (code,),
        ).fetchone()
        if row is None:
            set_cached_quota(code, -1)  # 缓存无效卡密
            return False, None, "卡密无效或额度不足"

        remaining = row["total_quota"] - row["used_quota"]
        if remaining <= 0:
            set_cached_quota(code, 0)
            return False, 0, "卡密无效或额度不足"

        # 原子扣减
        cursor = conn.execute(
            "UPDATE codes_table SET used_quota = used_quota + 1 "
            "WHERE code = ? AND (total_quota - used_quota) >= 1",
            (code,),
        )
        if cursor.rowcount == 0:
            set_cached_quota(code, 0)
            return False, 0, "卡密无效或额度不足"

        conn.commit()
        # 扣减后查询最新余额
        row = conn.execute(
            "SELECT total_quota, used_quota FROM codes_table WHERE code = ?",
            (code,),
        ).fetchone()
        final_remaining = row["total_quota"] - row["used_quota"]

        # 更新缓存
        invalidate_code(code)
        set_cached_quota(code, final_remaining)

        return True, final_remaining, "验证成功"


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
            ("TEST-CODE-001", 3, 0),
        )
        conn.commit()

    # 测试验证
    assert validate_code("TEST-CODE-001") is True
    assert validate_code("INVALID-CODE") is False
    print("[OK] 卡密验证通过")

    # 测试查询余额
    assert get_remaining_quota("TEST-CODE-001") == 3
    assert get_remaining_quota("INVALID-CODE") is None
    print("[OK] 余额查询通过")

    # 测试扣费
    assert deduct_quota("TEST-CODE-001", 1) is True
    assert get_remaining_quota("TEST-CODE-001") == 2
    assert deduct_quota("TEST-CODE-001", 3) is False  # 余额不足
    assert get_remaining_quota("TEST-CODE-001") == 2  # 未变化
    print("[OK] 扣费逻辑通过")

    # 测试 validate_and_deduct
    success, remaining, msg = validate_and_deduct("TEST-CODE-001")
    assert success is True
    assert remaining == 1
    assert msg == "验证成功"
    print("[OK] validate_and_deduct 通过")

    # 清理测试数据库
    try:
        os.remove(DB_PATH)
        print("[OK] 已清理测试数据库")
    except PermissionError:
        print("[跳过] 测试数据库被占用，可手动删除 test_database.db")
    print("[OK] 全部测试通过")
