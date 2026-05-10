"""卡密验证接口"""

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.db_manager import validate_and_deduct, get_next_beta_code
from backend.rate_limiter import rate_limit_check, record_failure, record_success

logger = logging.getLogger(__name__)

router = APIRouter()


class CodeRequest(BaseModel):
    code: str


class CodeResponse(BaseModel):
    success: bool
    message: str
    remaining_quota: int | None = None


@router.post("/validate-code", response_model=CodeResponse)
def validate_code_api(req: CodeRequest, request: Request):
    """验证卡密有效性并原子扣减 1 次配额，返回剩余额度"""
    code = req.code.strip()
    if not code:
        return CodeResponse(success=False, message="卡密无效或额度不足")

    # 速率限制检查
    client_ip = request.client.host if request.client else "unknown"
    limited, retry_msg = rate_limit_check(client_ip, code)
    if limited:
        logger.warning(f"[validate-code] 速率限制触发: ip={client_ip}, code='{code}'")
        return CodeResponse(success=False, message=retry_msg)

    logger.info(f"[validate-code] 请求: ip={client_ip}, code='{code}'")

    success, remaining, message = validate_and_deduct(code)
    logger.info(f"[validate-code] 结果: success={success}, remaining={remaining}")

    if success:
        record_success(code)
    else:
        record_failure(code)

    return CodeResponse(
        success=success,
        message=message,
        remaining_quota=remaining,
    )


@router.get("/next-beta-code")
def next_beta_code():
    """获取下一个有剩余额度的 BETA 测试卡密"""
    code = get_next_beta_code()
    if not code:
        return {"success": False, "code": None, "message": "暂无可用测试卡密"}
    return {"success": True, "code": code}
