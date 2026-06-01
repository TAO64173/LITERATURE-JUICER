"""Supabase client for user and quota management.

Uses the Supabase service role key (server-side only, never exposed to browser).
All operations degrade gracefully when Supabase is unavailable or tables are missing.
"""

from __future__ import annotations

import logging
import os
import time

from supabase import Client, create_client

logger = logging.getLogger(__name__)

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_client: Client | None = None
_supabase_available: bool | None = None  # None = not checked yet
_last_failure_time: float = 0
_RETRY_COOLDOWN = 60  # seconds before retrying after failure


def get_supabase() -> Client | None:
    """Return singleton Supabase client (service role), or None if unavailable."""
    global _client, _supabase_available, _last_failure_time

    if _supabase_available is False:
        # Allow retry after cooldown period (e.g., tables created while server running)
        if time.time() - _last_failure_time < _RETRY_COOLDOWN:
            return None
        logger.info("[supabase] Retrying connection after cooldown")
        _supabase_available = None
        _client = None

    if _client is None:
        if not _SUPABASE_URL or not _SUPABASE_SERVICE_KEY:
            _supabase_available = False
            _last_failure_time = time.time()
            logger.warning("Supabase env vars not set — quota system disabled")
            return None
        try:
            _client = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_KEY)
            _supabase_available = True
            logger.info("[supabase] Client connected successfully")
        except Exception as e:
            _supabase_available = False
            _last_failure_time = time.time()
            logger.warning("Supabase client creation failed: %s", e)
            return None
    return _client


def reset_supabase_cache() -> None:
    """Force reset the Supabase client cache. Useful after creating tables."""
    global _client, _supabase_available, _last_failure_time
    _client = None
    _supabase_available = None
    _last_failure_time = 0
    logger.info("[supabase] Cache reset")


def _retry_query(fn, *args, retries=3, **kwargs):
    """Execute a Supabase query with retry on transient SSL/connection errors."""
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if attempt < retries - 1 and ("ssl" in err_str or "eof" in err_str or "connectionterminated" in err_str or "connect" in err_str):
                logger.warning("[supabase] Retry %d/%d after transient error: %s", attempt + 1, retries, e)
                time.sleep(0.3 * (attempt + 1))
                continue
            raise


# Admin email — unlimited quota, no deductions
ADMIN_EMAIL = "2463776055@qq.com"

# Default quota when Supabase is unavailable — match new user signup (3 free uploads)
_DEFAULT_QUOTA = {"total_quota": 3, "used_quota": 0}


def is_admin(email: str) -> bool:
    """Check if the given email belongs to an admin user."""
    return email.lower() == ADMIN_EMAIL.lower()


def _admin_quota() -> dict:
    """Return the virtual quota dict for admin users."""
    return {"total_quota": 999999, "used_quota": 0}


def get_user_role(email: str) -> str:
    """Return 'admin' or 'user' based on email."""
    return "admin" if is_admin(email) else "user"


def ensure_user_and_quota(clerk_user_id: str, email: str) -> dict:
    """Get or create user + quota row. Returns quota dict with role info.

    Admin users get virtual unlimited quota (total_quota=999999, used_quota=0).
    Normal users get 3 free credits on first login.
    Falls back to default quota if Supabase is unavailable.
    """
    role = get_user_role(email)
    logger.info("[quota] ensure_user_and_quota: clerk_user_id=%s email=%s role=%s", clerk_user_id, email, role)

    # Admin: return virtual unlimited quota without touching DB
    if role == "admin":
        q = _admin_quota()
        q["role"] = "admin"
        logger.info("[quota] Admin user, returning unlimited quota")
        return q

    sb = get_supabase()
    if sb is None:
        logger.warning("[quota] Supabase unavailable, returning default quota")
        q = dict(_DEFAULT_QUOTA)
        q["role"] = "user"
        return q

    try:
        # Upsert user
        logger.info("[quota] Upserting user: clerk_user_id=%s email=%s", clerk_user_id, email)
        user_resp = _retry_query(
            sb.table("users")
            .upsert(
                {
                    "clerk_user_id": clerk_user_id,
                    "email": email or f"user_{clerk_user_id}@placeholder.local",
                    "role": role,
                },
                on_conflict="clerk_user_id",
            )
            .execute
        )
        if not user_resp.data:
            logger.warning("[quota] Supabase upsert user returned empty data")
            q = dict(_DEFAULT_QUOTA)
            q["role"] = "user"
            return q
        user = user_resp.data[0]
        logger.info("[quota] User upserted: id=%s", user["id"])

        # Check if quota already exists
        existing_quota = _retry_query(
            sb.table("quotas")
            .select("id, total_quota, used_quota")
            .eq("user_id", user["id"])
            .execute
        )

        if existing_quota.data:
            q = existing_quota.data[0]
            q["role"] = "user"
            logger.info("[quota] Existing quota found: total=%s used=%s", q["total_quota"], q["used_quota"])
            return q

        # First time: create quota row with 3 free credits
        logger.info("[quota] Creating new quota for user %s with 3 free credits", user["id"])
        quota_resp = _retry_query(
            sb.table("quotas")
            .insert(
                {
                    "user_id": user["id"],
                    "total_quota": 3,
                    "used_quota": 0,
                }
            )
            .execute
        )
        if not quota_resp.data:
            logger.warning("[quota] Supabase insert quota returned empty data")
            q = dict(_DEFAULT_QUOTA)
            q["role"] = "user"
            return q
        q = quota_resp.data[0]
        q["role"] = "user"
        logger.info("[quota] New quota created: total=%s used=%s", q["total_quota"], q["used_quota"])
        return q
    except Exception as e:
        logger.error("[quota] Supabase ensure_user_and_quota failed: %s", e, exc_info=True)
        q = dict(_DEFAULT_QUOTA)
        q["role"] = "user"
        return q


def get_remaining_quota(clerk_user_id: str, email: str = "") -> int | None:
    """Get remaining upload quota for a user. None if user not found.

    Admin users always get 999999 (unlimited).
    Returns 999 (unlimited) if Supabase is unavailable.
    """
    if is_admin(email):
        logger.info("[quota] get_remaining_quota: admin user, returning 999999")
        return 999999

    sb = get_supabase()
    if sb is None:
        logger.warning("[quota] get_remaining_quota: Supabase unavailable, returning default 3")
        return 3

    try:
        user_resp = (
            sb.table("users")
            .select("id")
            .eq("clerk_user_id", clerk_user_id)
            .execute()
        )
        if not user_resp.data:
            logger.info("[quota] get_remaining_quota: user not found for %s", clerk_user_id)
            return None

        user_id = user_resp.data[0]["id"]
        quota_resp = (
            sb.table("quotas")
            .select("total_quota, used_quota")
            .eq("user_id", user_id)
            .execute()
        )
        if not quota_resp.data:
            logger.info("[quota] get_remaining_quota: quota not found for user %s", user_id)
            return None

        q = quota_resp.data[0]
        remaining = q["total_quota"] - q["used_quota"]
        logger.info("[quota] get_remaining_quota: user=%s total=%s used=%s remaining=%s", clerk_user_id, q["total_quota"], q["used_quota"], remaining)
        return remaining
    except Exception as e:
        logger.warning("[quota] Supabase get_remaining_quota failed: %s", e)
        return 3


def deduct_quota(clerk_user_id: str, email: str = "") -> tuple[bool, int | None]:
    """Atomically deduct 1 from quota. Returns (success, remaining).

    Admin users are never deducted.
    Returns (True, 999999) for admin.
    Returns (True, 998) if Supabase is unavailable.
    """
    if is_admin(email):
        logger.info("[quota] deduct_quota: admin user, skipping deduction")
        return True, 999999

    sb = get_supabase()
    if sb is None:
        logger.warning("[quota] deduct_quota: Supabase unavailable, returning default 2")
        return True, 2

    try:
        user_resp = (
            sb.table("users")
            .select("id")
            .eq("clerk_user_id", clerk_user_id)
            .execute()
        )
        if not user_resp.data:
            logger.warning("[quota] deduct_quota: user not found for %s", clerk_user_id)
            return False, None

        user_id = user_resp.data[0]["id"]
        logger.info("[quota] deduct_quota: deducting 1 for user %s", user_id)

        # Use Postgres RPC for atomic decrement
        result = sb.rpc("deduct_quota", {"p_user_id": user_id}).execute()
        remaining = result.data

        if remaining is None or remaining < 0:
            logger.warning("[quota] deduct_quota: insufficient quota for user %s (remaining=%s)", user_id, remaining)
            return False, 0
        logger.info("[quota] deduct_quota: success, remaining=%s", remaining)
        return True, remaining
    except Exception as e:
        logger.warning("[quota] Supabase deduct_quota failed: %s", e)
        return True, 2


def deduct_quota_batch(clerk_user_id: str, count: int, email: str = "") -> tuple[bool, int | None]:
    """Atomically deduct N from quota. Returns (success, remaining).

    Admin users are never deducted.
    Returns (True, 999999) for admin.
    Returns (True, 998) if Supabase is unavailable.
    """
    if is_admin(email):
        logger.info("[quota] deduct_quota_batch: admin user, skipping deduction")
        return True, 999999

    if count <= 0:
        return True, None

    sb = get_supabase()
    if sb is None:
        logger.warning("[quota] deduct_quota_batch: Supabase unavailable, returning default")
        return True, max(0, 3 - count)

    try:
        user_resp = (
            sb.table("users")
            .select("id")
            .eq("clerk_user_id", clerk_user_id)
            .execute()
        )
        if not user_resp.data:
            logger.warning("[quota] deduct_quota_batch: user not found for %s", clerk_user_id)
            return False, None

        user_id = user_resp.data[0]["id"]
        logger.info("[quota] deduct_quota_batch: deducting %d for user %s", count, user_id)

        # Use Postgres RPC for atomic batch decrement
        result = sb.rpc("deduct_quota_batch", {"p_user_id": user_id, "p_count": count}).execute()
        remaining = result.data

        if remaining is None or remaining < 0:
            logger.warning("[quota] deduct_quota_batch: insufficient quota for user %s (remaining=%s)", user_id, remaining)
            return False, 0
        logger.info("[quota] deduct_quota_batch: success, remaining=%s", remaining)
        return True, remaining
    except Exception as e:
        logger.warning("[quota] Supabase deduct_quota_batch failed: %s", e)
        return True, max(0, 3 - count)


def create_history_record(clerk_user_id: str, filename: str) -> dict | None:
    """Insert a new analysis_history row with status='processing'.

    Returns the inserted record dict or None on failure.
    """
    sb = get_supabase()
    if sb is None:
        return None

    try:
        user_resp = (
            sb.table("users")
            .select("id")
            .eq("clerk_user_id", clerk_user_id)
            .execute()
        )
        if not user_resp.data:
            return None

        user_id = user_resp.data[0]["id"]
        resp = (
            sb.table("analysis_history")
            .insert({"user_id": user_id, "filename": filename, "status": "processing"})
            .execute()
        )
        if not resp.data:
            return None
        return resp.data[0]
    except Exception as e:
        logger.warning("Supabase create_history_record failed: %s", e)
        return None


def update_history_status(
    record_id: str, status: str, result_url: str | None = None
) -> None:
    """Update an analysis_history row. Best-effort, never raises."""
    sb = get_supabase()
    if sb is None:
        return

    try:
        update_fields: dict = {"status": status}
        if result_url is not None:
            update_fields["result_url"] = result_url
        sb.table("analysis_history").update(update_fields).eq("id", record_id).execute()
    except Exception as e:
        logger.warning("Supabase update_history_status failed: %s", e)


def get_history(clerk_user_id: str) -> list[dict]:
    """Return analysis history for a user, newest first.

    Returns empty list on any failure.
    """
    sb = get_supabase()
    if sb is None:
        return []

    try:
        user_resp = (
            sb.table("users")
            .select("id")
            .eq("clerk_user_id", clerk_user_id)
            .execute()
        )
        if not user_resp.data:
            return []

        user_id = user_resp.data[0]["id"]
        resp = (
            sb.table("analysis_history")
            .select("id, filename, status, result_url, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        logger.warning("Supabase get_history failed: %s", e)
        return []


def log_usage(clerk_user_id: str, files_count: int) -> None:
    """Record a usage history entry. Best-effort, never raises."""
    sb = get_supabase()
    if sb is None:
        return

    try:
        user_resp = (
            sb.table("users")
            .select("id")
            .eq("clerk_user_id", clerk_user_id)
            .execute()
        )
        if not user_resp.data:
            return

        user_id = user_resp.data[0]["id"]
        sb.table("usage_history").insert(
            {"user_id": user_id, "files_count": files_count}
        ).execute()
    except Exception:
        pass


# ─── Invite System ──────────────────────────────────────────────

import random
import string


def _generate_invite_code() -> str:
    """Generate a random 5-character uppercase alphanumeric invite code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=5))


def generate_user_invite_code(clerk_user_id: str, email: str) -> str:
    """Generate and store a unique invite code for a user. Returns existing code if already generated."""
    if is_admin(email):
        return "ADMIN0"

    sb = get_supabase()
    if sb is None:
        return ""

    try:
        # Check if user already has an invite code
        user_resp = _retry_query(
            sb.table("users")
            .select("id, invite_code")
            .eq("clerk_user_id", clerk_user_id)
            .execute
        )
        if not user_resp.data:
            return ""
        user = user_resp.data[0]
        if user.get("invite_code"):
            return user["invite_code"]

        # Generate unique code (retry on collision)
        for _ in range(10):
            code = _generate_invite_code()
            existing = _retry_query(sb.table("users").select("id").eq("invite_code", code).execute)
            if not existing.data:
                _retry_query(sb.table("users").update({"invite_code": code}).eq("id", user["id"]).execute)
                logger.info("[invite] Generated invite code %s for user %s", code, clerk_user_id)
                return code

        logger.warning("[invite] Failed to generate unique invite code after 10 attempts")
        return ""
    except Exception as e:
        logger.warning("[invite] generate_user_invite_code failed: %s", e)
        return ""


def get_invite_info(clerk_user_id: str, email: str) -> dict:
    """Get user's invite code and how many people they've invited."""
    if is_admin(email):
        return {"invite_code": "ADMIN0", "invited_count": 0}

    sb = get_supabase()
    if sb is None:
        return {"invite_code": "", "invited_count": 0}

    try:
        user_resp = _retry_query(
            sb.table("users")
            .select("id, invite_code")
            .eq("clerk_user_id", clerk_user_id)
            .execute
        )
        if not user_resp.data:
            return {"invite_code": "", "invited_count": 0}
        user = user_resp.data[0]
        invite_code = user.get("invite_code") or ""

        if not invite_code:
            invite_code = generate_user_invite_code(clerk_user_id, email)

        # Count invited users
        count_resp = _retry_query(
            sb.table("invite_records")
            .select("id", count="exact")
            .eq("inviter_user_id", user["id"])
            .execute
        )
        invited_count = count_resp.count or 0

        return {"invite_code": invite_code, "invited_count": invited_count}
    except Exception as e:
        logger.warning("[invite] get_invite_info failed: %s", e)
        return {"invite_code": "", "invited_count": 0}


def apply_invite_code(clerk_user_id: str, email: str, invite_code: str) -> dict:
    """Apply an invite code. Only the inviter gets +2 quota. Returns result dict."""
    if not invite_code or len(invite_code) != 5:
        return {"success": False, "message": "邀请码格式无效"}

    sb = get_supabase()
    if sb is None:
        return {"success": False, "message": "服务暂时不可用"}

    try:
        # Find the invited user
        invited_resp = (
            sb.table("users")
            .select("id, invited_by")
            .eq("clerk_user_id", clerk_user_id)
            .execute()
        )
        if not invited_resp.data:
            return {"success": False, "message": "用户不存在"}
        invited_user = invited_resp.data[0]

        # Already invited?
        if invited_user.get("invited_by"):
            return {"success": False, "message": "你已经使用过邀请码了"}

        # Find inviter by invite code
        inviter_resp = (
            sb.table("users")
            .select("id, clerk_user_id, email")
            .eq("invite_code", invite_code.upper())
            .execute()
        )
        if not inviter_resp.data:
            return {"success": False, "message": "邀请码不存在"}
        inviter = inviter_resp.data[0]

        # Cannot invite yourself
        if inviter["id"] == invited_user["id"]:
            return {"success": False, "message": "不能使用自己的邀请码"}

        # Admin cannot be inviter
        if is_admin(inviter.get("email", "")):
            return {"success": False, "message": "该邀请码不可用"}

        # Mark invited user
        sb.table("users").update({
            "invited_by": invite_code.upper(),
            "invite_rewarded": True,
        }).eq("id", invited_user["id"]).execute()

        # Add +2 quota to inviter
        result = sb.rpc("add_quota", {"p_user_id": inviter["id"], "p_amount": 2}).execute()
        if result.data is None or result.data < 0:
            logger.warning("[invite] add_quota failed for inviter %s", inviter["id"])

        # Record the invite
        sb.table("invite_records").insert({
            "inviter_user_id": inviter["id"],
            "invited_user_id": invited_user["id"],
            "invite_code": invite_code.upper(),
            "reward_quota": 2,
        }).execute()

        logger.info("[invite] User %s applied invite code %s from %s", clerk_user_id, invite_code, inviter["clerk_user_id"])
        return {"success": True, "message": "邀请码使用成功！邀请人已获得 2 篇额度"}
    except Exception as e:
        logger.error("[invite] apply_invite_code failed: %s", e, exc_info=True)
        return {"success": False, "message": "邀请码使用失败，请稍后重试"}


# ─── Order Management (Mapay EPay) ───────────────────────────────

def get_user_id_by_clerk_id(clerk_user_id: str) -> str | None:
    """Look up internal user UUID by Clerk user ID."""
    sb = get_supabase()
    if sb is None:
        return None
    try:
        resp = sb.table("users").select("id").eq("clerk_user_id", clerk_user_id).execute()
        if resp.data:
            return resp.data[0]["id"]
        return None
    except Exception as e:
        logger.warning("[order] get_user_id_by_clerk_id failed: %s", e)
        return None


def create_order(user_id: str, amount: float, credits: int, order_id: str) -> dict | None:
    """Insert a new order row with status='pending'. Returns the order dict or None."""
    sb = get_supabase()
    if sb is None:
        return None
    try:
        resp = sb.table("orders").insert({
            "id": order_id,
            "user_id": user_id,
            "amount": amount,
            "credits": credits,
            "status": "pending",
        }).execute()
        if resp.data:
            return resp.data[0]
        return None
    except Exception as e:
        logger.error("[order] create_order failed: %s", e, exc_info=True)
        return None


def get_order(order_id: str) -> dict | None:
    """Fetch an order by ID."""
    sb = get_supabase()
    if sb is None:
        return None
    try:
        resp = sb.table("orders").select("*").eq("id", order_id).execute()
        if resp.data:
            return resp.data[0]
        return None
    except Exception as e:
        logger.warning("[order] get_order failed: %s", e)
        return None


def update_order_status(order_id: str, status: str, provider_order_id: str | None = None) -> bool:
    """Update order status (and optionally provider_order_id). Returns True on success."""
    sb = get_supabase()
    if sb is None:
        return False
    try:
        update: dict = {"status": status}
        if provider_order_id is not None:
            update["provider_order_id"] = provider_order_id
        sb.table("orders").update(update).eq("id", order_id).execute()
        return True
    except Exception as e:
        logger.warning("[order] update_order_status failed: %s", e)
        return False
