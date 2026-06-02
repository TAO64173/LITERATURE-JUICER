"""Payment API — Mapay EPay integration."""
from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel

from backend.auth import verify_clerk_token
from backend.supabase_client import (
    create_order,
    get_order,
    get_user_id_by_clerk_id,
    update_order_status,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_PAY_PID = os.environ.get("PAY_PID", "")
_PAY_KEY = os.environ.get("PAY_KEY", "")
_PAY_API = os.environ.get("PAY_API", "https://mzf.mapay.cc/xpay/epay/submit.php")
_PAY_NOTIFY_URL = os.environ.get("PAY_NOTIFY_URL", "")
_PAY_RETURN_URL = os.environ.get("PAY_RETURN_URL", "")

logger.info("[payment] Config loaded: PID=%s KEY_LEN=%d KEY_HEAD=%s KEY_TAIL=%s API=%s",
            _PAY_PID, len(_PAY_KEY), _PAY_KEY[:3] if _PAY_KEY else "",
            _PAY_KEY[-3:] if _PAY_KEY else "", _PAY_API)

# Amount (yuan) → credits mapping
_AMOUNT_CREDITS = {
    8.8: 10,
    15: 20,
}


def _sign_params(params: dict[str, str]) -> str:
    """MD5 sign per Mapay EPay doc: sort params, join with &, append KEY directly, lowercase md5."""
    filtered = {k: v for k, v in params.items() if v and k not in ("sign", "sign_type")}
    query = "&".join(f"{k}={v}" for k, v in sorted(filtered.items()))
    raw = query + _PAY_KEY  # 直接拼接 KEY，不加 &key=
    logger.info("[payment] Sign raw: %s", raw)
    sign = hashlib.md5(raw.encode("utf-8")).hexdigest()  # 小写
    logger.info("[payment] Sign result: %s", sign)
    return sign


# ── Create Order ──────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    amount: float


@router.post("/payment/create")
def create_payment_order(
    req: CreateOrderRequest,
    token_payload: dict = Depends(verify_clerk_token),
):
    if not _PAY_PID or not _PAY_KEY:
        logger.error("[payment] PAY_PID or PAY_KEY not configured!")
        return {"success": False, "message": "支付未配置，请联系管理员"}

    clerk_user_id = token_payload.get("sub", "")
    credits = _AMOUNT_CREDITS.get(req.amount)
    if not credits:
        return {"success": False, "message": "无效的套餐"}

    user_id = get_user_id_by_clerk_id(clerk_user_id)
    if not user_id:
        return {"success": False, "message": "用户不存在"}

    order_id = f"LJ{int(time.time())}{uuid.uuid4().hex[:6].upper()}"

    order = create_order(user_id, req.amount, credits, order_id)
    if not order:
        return {"success": False, "message": "创建订单失败，请稍后重试"}

    # Build signed payment URL
    money = f"{req.amount:.2f}"  # Ensure 2 decimal places: 8.8 → "8.80"
    params = {
        "pid": _PAY_PID.strip(),
        "out_trade_no": order_id,
        "notify_url": _PAY_NOTIFY_URL.strip(),
        "return_url": _PAY_RETURN_URL.strip(),
        "name": f"LiteratureJuicer-x{credits}",
        "money": money,
        "type": "alipay",
    }
    params["sign"] = _sign_params(params)
    params["sign_type"] = "MD5"

    qs = "&".join(f"{k}={v}" for k, v in params.items())
    pay_url = f"{_PAY_API}?{qs}"
    logger.info("[payment] Pay URL: %s", pay_url)

    logger.info("[payment] Order created: %s amount=%.1f credits=%d", order_id, req.amount, credits)
    return {"success": True, "payUrl": pay_url, "orderId": order_id}


# ── Payment Callback (async POST from Mapay) ─────────────────────

@router.post("/payment/notify")
async def payment_notify(request: Request):
    # EPay sends params as query string
    params = dict(request.query_params)
    logger.info("[payment] Notify received: %s", params)

    # 1. Verify signature
    sign = params.get("sign", "")
    expected = _sign_params(params)
    if sign != expected:
        logger.warning("[payment] Signature mismatch: got=%s expected=%s", sign, expected)
        return PlainTextResponse("fail")

    trade_status = params.get("trade_status", "")
    if trade_status != "TRADE_SUCCESS":
        logger.info("[payment] Ignoring status: %s", trade_status)
        return PlainTextResponse("fail")

    order_id = params.get("out_trade_no", "")
    trade_no = params.get("trade_no", "")

    # 2. Fetch order
    order = get_order(order_id)
    if not order:
        logger.warning("[payment] Order not found: %s", order_id)
        return PlainTextResponse("fail")

    # 3. Prevent duplicate processing
    if order["status"] != "pending":
        logger.info("[payment] Order already processed: %s status=%s", order_id, order["status"])
        return PlainTextResponse("success")

    # 4. Add credits FIRST (if this fails, order stays pending, Mapay will retry)
    try:
        from backend.supabase_client import get_supabase

        sb = get_supabase()
        if sb:
            result = sb.rpc("add_quota", {
                "p_user_id": order["user_id"],
                "p_amount": order["credits"],
            }).execute()
            if result.data is None or result.data < 0:
                logger.error("[payment] add_quota returned invalid: %s", result.data)
                return PlainTextResponse("fail")
            logger.info("[payment] Credits added: order=%s credits=%d remaining=%s",
                        order_id, order["credits"], result.data)
        else:
            logger.error("[payment] Supabase unavailable, cannot add credits")
            return PlainTextResponse("fail")
    except Exception as e:
        logger.error("[payment] Failed to add credits: %s", e, exc_info=True)
        return PlainTextResponse("fail")

    # 5. Update order status AFTER credits added successfully
    update_order_status(order_id, "paid", trade_no)

    return PlainTextResponse("success")


# ── Return URL (browser redirect from Mapay) ─────────────────────

@router.get("/payment/return")
def payment_return(order_id: str = ""):
    """Redirect user to frontend success page after payment."""
    frontend = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")[0].strip()
    return RedirectResponse(url=f"{frontend}/payment/success?orderId={order_id}")


# ── Query Payment Status ─────────────────────────────────────────

@router.get("/payment/status/{order_id}")
def payment_status(order_id: str, token_payload: dict = Depends(verify_clerk_token)):
    clerk_user_id = token_payload.get("sub", "")

    order = get_order(order_id)
    if not order:
        return {"success": False, "message": "订单不存在"}

    # Verify order belongs to requesting user
    user_id = get_user_id_by_clerk_id(clerk_user_id)
    if order["user_id"] != user_id:
        return {"success": False, "message": "无权查看此订单"}

    paid = order["status"] == "paid"
    return {"success": True, "paid": paid, "credits": order["credits"] if paid else 0}
