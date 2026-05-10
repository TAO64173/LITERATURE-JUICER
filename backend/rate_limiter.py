"""
内存速率限制器（滑动窗口）
适用于 Render 单 Worker 部署场景
"""

import time
import threading
from collections import defaultdict

# 配置
IP_RATE_LIMIT = 10       # 同 IP 每分钟最大请求数
IP_WINDOW_SECONDS = 60   # IP 限流窗口
CODE_FAIL_THRESHOLD = 5  # 同一卡密连续失败次数阈值
CODE_BAN_SECONDS = 300   # 卡密封禁时长（5 分钟）

# 存储结构：{key: [timestamp, ...]}
_ip_requests: dict[str, list[float]] = defaultdict(list)
_code_failures: dict[str, list[float]] = defaultdict(list)
_code_bans: dict[str, float] = {}

_lock = threading.Lock()


def _cleanup_window(entries: list[float], window: float) -> list[float]:
    """清理过期时间戳"""
    now = time.monotonic()
    return [t for t in entries if now - t < window]


def rate_limit_check(ip: str, code: str) -> tuple[bool, str]:
    """
    检查速率限制
    返回 (is_limited, message)
    """
    now = time.monotonic()

    with _lock:
        # 1. 检查卡密是否被封禁
        if code in _code_bans:
            if now < _code_bans[code]:
                remaining = int(_code_bans[code] - now)
                return True, f"该卡密已被临时封禁，请 {remaining} 秒后重试"
            else:
                del _code_bans[code]
                _code_failures.pop(code, None)

        # 2. IP 速率限制
        _ip_requests[ip] = _cleanup_window(_ip_requests[ip], IP_WINDOW_SECONDS)
        if len(_ip_requests[ip]) >= IP_RATE_LIMIT:
            return True, "请求过于频繁，请稍后再试"
        _ip_requests[ip].append(now)

    return False, ""


def record_failure(code: str) -> None:
    """记录卡密验证失败，超过阈值则封禁"""
    now = time.monotonic()

    with _lock:
        _code_failures[code] = _cleanup_window(
            _code_failures[code], IP_WINDOW_SECONDS
        )
        _code_failures[code].append(now)

        if len(_code_failures[code]) >= CODE_FAIL_THRESHOLD:
            _code_bans[code] = now + CODE_BAN_SECONDS
            _code_failures.pop(code, None)


def record_success(code: str) -> None:
    """验证成功时清除失败记录"""
    with _lock:
        _code_failures.pop(code, None)


def get_stats() -> dict:
    """获取限流器状态（调试用）"""
    with _lock:
        return {
            "tracked_ips": len(_ip_requests),
            "tracked_codes": len(_code_failures),
            "banned_codes": len(_code_bans),
        }
