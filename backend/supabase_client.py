"""Supabase client for user and quota management.

Uses the Supabase service role key (server-side only, never exposed to browser).
All operations degrade gracefully when Supabase is unavailable or tables are missing.
"""

from __future__ import annotations

import logging
import os

from supabase import Client, create_client

logger = logging.getLogger(__name__)

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_client: Client | None = None
_supabase_available: bool | None = None  # None = not checked yet


def get_supabase() -> Client | None:
    """Return singleton Supabase client (service role), or None if unavailable."""
    global _client, _supabase_available
    if _supabase_available is False:
        return None
    if _client is None:
        if not _SUPABASE_URL or not _SUPABASE_SERVICE_KEY:
            _supabase_available = False
            logger.warning("Supabase env vars not set — quota system disabled")
            return None
        try:
            _client = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_KEY)
            _supabase_available = True
        except Exception as e:
            _supabase_available = False
            logger.warning("Supabase client creation failed: %s", e)
            return None
    return _client


# Default quota when Supabase is unavailable
_DEFAULT_QUOTA = {"total_quota": 999, "used_quota": 0}


def ensure_user_and_quota(clerk_user_id: str, email: str) -> dict:
    """Get or create user + quota row. Returns quota dict.

    Falls back to default quota if Supabase is unavailable.
    """
    sb = get_supabase()
    if sb is None:
        return dict(_DEFAULT_QUOTA)

    try:
        # Upsert user
        user_resp = (
            sb.table("users")
            .upsert(
                {"clerk_user_id": clerk_user_id, "email": email},
                on_conflict="clerk_user_id",
            )
            .execute()
        )
        if not user_resp.data:
            logger.warning("Supabase upsert user returned empty data")
            return dict(_DEFAULT_QUOTA)
        user = user_resp.data[0]

        # Check if quota already exists
        existing_quota = (
            sb.table("quotas")
            .select("id, total_quota, used_quota")
            .eq("user_id", user["id"])
            .execute()
        )

        if existing_quota.data:
            return existing_quota.data[0]

        # First time: create quota row
        quota_resp = (
            sb.table("quotas")
            .insert(
                {
                    "user_id": user["id"],
                    "total_quota": 3,
                    "used_quota": 0,
                }
            )
            .execute()
        )
        if not quota_resp.data:
            logger.warning("Supabase insert quota returned empty data")
            return dict(_DEFAULT_QUOTA)
        return quota_resp.data[0]
    except Exception as e:
        logger.warning("Supabase ensure_user_and_quota failed: %s", e)
        return dict(_DEFAULT_QUOTA)


def get_remaining_quota(clerk_user_id: str) -> int | None:
    """Get remaining upload quota for a user. None if user not found.

    Returns 999 (unlimited) if Supabase is unavailable.
    """
    sb = get_supabase()
    if sb is None:
        return 999

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
        quota_resp = (
            sb.table("quotas")
            .select("total_quota, used_quota")
            .eq("user_id", user_id)
            .execute()
        )
        if not quota_resp.data:
            return None

        q = quota_resp.data[0]
        return q["total_quota"] - q["used_quota"]
    except Exception as e:
        logger.warning("Supabase get_remaining_quota failed: %s", e)
        return 999


def deduct_quota(clerk_user_id: str) -> tuple[bool, int | None]:
    """Atomically deduct 1 from quota. Returns (success, remaining).

    Returns (True, 998) if Supabase is unavailable.
    """
    sb = get_supabase()
    if sb is None:
        return True, 998

    try:
        user_resp = (
            sb.table("users")
            .select("id")
            .eq("clerk_user_id", clerk_user_id)
            .execute()
        )
        if not user_resp.data:
            return False, None

        user_id = user_resp.data[0]["id"]

        # Use Postgres RPC for atomic decrement
        result = sb.rpc("deduct_quota", {"p_user_id": user_id}).execute()
        remaining = result.data

        if remaining is None or remaining < 0:
            return False, 0
        return True, remaining
    except Exception as e:
        logger.warning("Supabase deduct_quota failed: %s", e)
        return True, 998


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
