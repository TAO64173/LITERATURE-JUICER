"""批量生成测试卡密 BETA001~BETA100，写入数据库并导出 txt"""

import sys
from pathlib import Path

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.db_manager import get_connection, init_db

CODES = [f"BETA{i:03d}" for i in range(1, 101)]
QUOTA = 3


def main() -> None:
    init_db()

    with get_connection() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO codes_table (code, total_quota, used_quota) VALUES (?, ?, ?)",
            [(code, QUOTA, 0) for code in CODES],
        )
        conn.commit()

    # 导出 txt
    txt_path = Path(__file__).parent.parent / "beta_codes.txt"
    txt_path.write_text("\n".join(CODES) + "\n", encoding="utf-8")

    print(f"已写入 {len(CODES)} 个卡密到数据库")
    print(f"已导出到 {txt_path}")


if __name__ == "__main__":
    main()
