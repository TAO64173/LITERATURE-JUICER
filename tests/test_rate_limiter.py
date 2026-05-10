"""速率限制器测试"""

import time
import pytest
from backend import rate_limiter


@pytest.fixture(autouse=True)
def reset_limiter():
    """每个测试前重置限流器状态"""
    rate_limiter._ip_requests.clear()
    rate_limiter._code_failures.clear()
    rate_limiter._code_bans.clear()
    yield
    rate_limiter._ip_requests.clear()
    rate_limiter._code_failures.clear()
    rate_limiter._code_bans.clear()


class TestRateLimitCheck:
    def test_first_request_not_limited(self):
        limited, msg = rate_limiter.rate_limit_check("1.2.3.4", "CODE1")
        assert limited is False

    def test_ip_rate_limit_exceeded(self):
        ip = "10.0.0.1"
        for _ in range(10):
            rate_limiter.rate_limit_check(ip, "CODE1")

        limited, msg = rate_limiter.rate_limit_check(ip, "CODE1")
        assert limited is True
        assert "频繁" in msg

    def test_different_ips_independent(self):
        for _ in range(10):
            rate_limiter.rate_limit_check("10.0.0.1", "CODE1")

        limited, _ = rate_limiter.rate_limit_check("10.0.0.2", "CODE1")
        assert limited is False

    def test_banned_code_rejected(self):
        rate_limiter._code_bans["BANNED"] = time.monotonic() + 60
        limited, msg = rate_limiter.rate_limit_check("1.2.3.4", "BANNED")
        assert limited is True
        assert "封禁" in msg


class TestRecordFailure:
    def test_ban_after_threshold(self):
        code = "FAILCODE"
        for _ in range(5):
            rate_limiter.record_failure(code)

        assert code in rate_limiter._code_bans

    def test_success_clears_failures(self):
        code = "FAILCODE"
        for _ in range(3):
            rate_limiter.record_failure(code)

        rate_limiter.record_success(code)
        assert code not in rate_limiter._code_failures


class TestGetStats:
    def test_returns_stats(self):
        stats = rate_limiter.get_stats()
        assert "tracked_ips" in stats
        assert "tracked_codes" in stats
        assert "banned_codes" in stats
