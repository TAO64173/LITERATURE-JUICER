"""卡密验证接口"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from backend.db_manager import validate_code, get_remaining_quota, get_next_beta_code

logger = logging.getLogger(__name__)

router = APIRouter()


class CodeRequest(BaseModel):
    code: str


class CodeResponse(BaseModel):
    success: bool
    message: str
    remaining_quota: int | None = None


@router.post("/validate-code", response_model=CodeResponse)
def validate_code_api(req: CodeRequest):
    """验证卡密有效性，返回剩余额度"""
    code = req.code.strip()
    logger.info(f"[validate-code] 收到请求: code='{code}'")

    exists = validate_code(code)
    logger.info(f"[validate-code] DB 查询 exists={exists}")

    if not exists:
        logger.info(f"[validate-code] 卡密不存在，返回失败")
        return CodeResponse(success=False, message="卡密无效或额度不足")

    remaining = get_remaining_quota(code)
    logger.info(f"[validate-code] remaining={remaining}")

    if remaining <= 0:
        logger.info(f"[validate-code] 额度不足，返回失败")
        return CodeResponse(success=False, message="卡密无效或额度不足")

    logger.info(f"[validate-code] 验证成功, remaining={remaining}")
    return CodeResponse(
        success=True,
        message="验证成功",
        remaining_quota=remaining,
    )


@router.get("/next-beta-code")
def next_beta_code():
    """获取下一个有剩余额度的 BETA 测试卡密"""
    code = get_next_beta_code()
    if not code:
        return {"success": False, "code": None, "message": "暂无可用测试卡密"}
    return {"success": True, "code": code}
