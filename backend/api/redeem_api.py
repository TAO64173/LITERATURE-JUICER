"""Redeem code and payment placeholder API endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.auth import verify_clerk_token
from backend.supabase_client import ensure_user_and_quota, redeem_code

logger = logging.getLogger(__name__)

router = APIRouter()


class RedeemRequest(BaseModel):
    code: str


@router.post("/redeem")
def redeem(
    req: RedeemRequest,
    token_payload: dict = Depends(verify_clerk_token),
):
    """Redeem a prepaid code for quota."""
    clerk_user_id = token_payload.get("sub", "")
    email = token_payload.get("email", "")
    logger.info("[redeem-api] Request: code=%s user=%s email=%s", req.code, clerk_user_id, email)

    # Ensure user exists in Supabase before redeeming
    ensure_user_and_quota(clerk_user_id, email)

    result = redeem_code(clerk_user_id, email, req.code)
    logger.info("[redeem-api] Result: %s", result)
    return result


@router.post("/payment/create-order")
def create_order():
    """Mock payment endpoint — returns a fake order ID. Real payment integration later."""
    order_id = f"MOCK_{uuid.uuid4().hex[:8].upper()}"
    logger.info("[payment] Mock order created: %s", order_id)
    return {
        "success": True,
        "order_id": order_id,
        "message": "模拟订单创建成功（支付功能暂未开放）",
    }
