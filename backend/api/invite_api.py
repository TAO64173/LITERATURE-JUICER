"""Invite/referral API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.auth import verify_clerk_token
from backend.supabase_client import apply_invite_code, ensure_user_and_quota, generate_user_invite_code, get_invite_info

logger = logging.getLogger(__name__)

router = APIRouter()


class ApplyInviteRequest(BaseModel):
    code: str


@router.get("/invite/info")
def invite_info(token_payload: dict = Depends(verify_clerk_token)):
    """Get the current user's invite code and invited count."""
    clerk_user_id = token_payload.get("sub", "")
    email = token_payload.get("email", "")

    # Ensure user exists in Supabase before querying invite info
    ensure_user_and_quota(clerk_user_id, email)

    info = get_invite_info(clerk_user_id, email)
    return {
        "success": True,
        "invite_code": info["invite_code"],
        "invited_count": info["invited_count"],
    }


@router.post("/invite/apply")
def apply_invite(
    req: ApplyInviteRequest,
    token_payload: dict = Depends(verify_clerk_token),
):
    """Apply an invite code. Only the inviter gets +2 quota."""
    clerk_user_id = token_payload.get("sub", "")
    email = token_payload.get("email", "")

    # Ensure user exists in Supabase before applying invite
    ensure_user_and_quota(clerk_user_id, email)
    generate_user_invite_code(clerk_user_id, email)

    result = apply_invite_code(clerk_user_id, email, req.code)
    return result
