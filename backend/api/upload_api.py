"""PDF 上传 + 处理 + 导出接口"""

import gc
import logging
import os
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import FileResponse

import fitz  # PyMuPDF

from backend.core.pdf_parser import extract_text
from backend.core.llm_engine import extract_paper_info
from backend.core.excel_writer import write_excel
from backend.auth import verify_clerk_token
from backend.supabase_client import ensure_user_and_quota, get_remaining_quota, deduct_quota_batch, log_usage, create_history_record, update_history_status, get_history, get_user_role

logger = logging.getLogger(__name__)

router = APIRouter()

# 目录配置
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# 限制常量
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_PAGES = 30
MAX_FILES = 20


def _validate_pdf(file_bytes: bytes, filename: str) -> str | None:
    """校验单个 PDF 文件，返回错误信息或 None"""
    if not filename.lower().endswith(".pdf"):
        return f"文件 {filename} 不是 PDF 格式"

    if len(file_bytes) > MAX_FILE_SIZE:
        return f"文件 {filename} 超过 10MB 限制"

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = doc.page_count
        doc.close()
        if page_count > MAX_PAGES:
            return f"文件 {filename} 超过 30 页限制（当前 {page_count} 页）"
    except Exception:
        return f"文件 {filename} 不是有效的 PDF 文件"

    return None


def _process_single_pdf(filepath: Path, filename: str) -> dict:
    """处理单个 PDF：解析 → LLM 提取 → 返回结构化数据（不会抛出异常）"""
    try:
        text = extract_text(str(filepath))
    except Exception as e:
        # PDF 文本提取失败，使用降级结果
        from backend.core.llm_engine import _build_fallback_result
        info = _build_fallback_result(filename)
        info["title"] = filename.replace(".pdf", "").replace("_", " ")
        info["_fallback"] = True
        info["_fallback_reason"] = f"PDF 文本提取失败: {str(e)}"
        return info

    info = extract_paper_info(text, filename=filename)
    info["title"] = filename.replace(".pdf", "").replace("_", " ")

    # 检测是否使用了降级模式
    if info.get("question") == "未成功解析":
        info["_fallback"] = True
        info["_fallback_reason"] = "LLM 返回内容无法解析为有效 JSON"
    else:
        info["_fallback"] = False

    return info


@router.post("/upload")
async def upload_pdfs(
    files: list[UploadFile] = File(...),
    token_payload: dict = Depends(verify_clerk_token),
):
    """批量上传 PDF → 解析 → LLM 提取 → 生成 Excel

    Requires Clerk JWT in Authorization header.
    Checks and deducts upload quota via Supabase.
    """
    clerk_user_id = token_payload.get("sub", "")
    email = token_payload.get("email", "")
    role = get_user_role(email)

    logger.info("[upload] Upload request: user=%s email=%s role=%s files=%d", clerk_user_id, email, role, len(files))

    # Ensure user + quota exist in Supabase
    try:
        quota_info = ensure_user_and_quota(clerk_user_id, email)
        logger.info("[upload] User quota initialized: %s", quota_info)
    except Exception as e:
        logger.error("[upload] User init failed: %s", e, exc_info=True)
        return {
            "success": False,
            "download_url": "",
            "results": [],
            "errors": [f"用户初始化失败: {str(e)}"],
            "warnings": [],
        }

    # Admin bypasses all quota checks
    if role != "admin":
        remaining = get_remaining_quota(clerk_user_id, email)
        if remaining is not None and remaining <= 0:
            return {
                "success": False,
                "download_url": "",
                "results": [],
                "errors": ["额度不足"],
                "warnings": [],
            }

    try:
        # === 文件数量校验 ===
        if len(files) > MAX_FILES:
            return {
                "success": False,
                "download_url": "",
                "results": [],
                "errors": [f"最多上传 {MAX_FILES} 个文件"],
                "warnings": [],
            }

        # === 额度预检（管理员跳过） ===
        remaining_now = None
        if role != "admin":
            remaining_now = get_remaining_quota(clerk_user_id, email)
            if remaining_now is not None and len(files) > remaining_now:
                return {
                    "success": False,
                    "download_url": "",
                    "results": [],
                    "errors": ["额度不足"],
                    "warnings": [],
                    "remaining_quota": remaining_now,
                }

        # === 阶段 1：校验并保存文件 ===
        saved_files: list[str] = []
        errors: list[str] = []

        for file in files:
            file_bytes = await file.read()
            error = _validate_pdf(file_bytes, file.filename)
            if error:
                errors.append(error)
                continue
            save_path = UPLOAD_DIR / file.filename
            with open(save_path, "wb") as f:
                f.write(file_bytes)
            saved_files.append(file.filename)

        if not saved_files:
            return {
                "success": False,
                "download_url": "",
                "results": [],
                "errors": errors,
                "warnings": [],
            }

        # === 创建历史记录 ===
        history_ids: list[str | None] = []
        for filename in saved_files:
            record = create_history_record(clerk_user_id, filename)
            history_ids.append(record["id"] if record else None)

        # === 阶段 2：逐个处理 PDF ===
        results: list[dict] = []
        success_count = 0
        process_errors: list[str] = []
        fallback_warnings: list[str] = []
        total = len(saved_files)

        for idx, filename in enumerate(saved_files):
            filepath = UPLOAD_DIR / filename
            try:
                result = _process_single_pdf(filepath, filename)

                is_fallback = result.pop("_fallback", False)
                result.pop("_fallback_reason", None)

                if is_fallback:
                    warning_msg = f"部分字段解析失败，已使用降级模式生成结果: {filename}"
                    fallback_warnings.append(warning_msg)
                else:
                    success_count += 1

                results.append(result)
                if history_ids[idx]:
                    update_history_status(history_ids[idx], "completed", "/download/literature_matrix.xlsx")
            except Exception as e:
                process_errors.append(f"处理 {filename} 失败: {str(e)}")
                if history_ids[idx]:
                    update_history_status(history_ids[idx], "failed")

        if not results:
            return {
                "success": False,
                "download_url": "",
                "results": [],
                "errors": errors + process_errors,
                "warnings": fallback_warnings,
            }

        # === 阶段 3：写入 Excel ===
        output_filename = "literature_matrix.xlsx"
        output_path = OUTPUT_DIR / output_filename
        write_excel(results, str(output_path))

        # === 扣减额度（管理员不扣减，只扣减成功解析的论文） ===
        new_remaining = None
        if role != "admin" and success_count > 0:
            try:
                _, new_remaining = deduct_quota_batch(
                    clerk_user_id, success_count, email
                )
            except Exception:
                new_remaining = None

        # === 记录使用历史 ===
        log_usage(clerk_user_id, success_count)

        return {
            "success": True,
            "download_url": f"/download/{output_filename}",
            "results": results,
            "errors": errors + process_errors,
            "warnings": fallback_warnings,
            "remaining_quota": new_remaining,
        }

    except Exception as e:
        logger.error("[upload] processing error: %s", e, exc_info=True)
        return {
            "success": False,
            "download_url": "",
            "results": [],
            "errors": [f"处理异常: {str(e)}"],
            "warnings": [],
        }

    finally:
        gc.collect()


@router.get("/quota")
async def get_quota(token_payload: dict = Depends(verify_clerk_token)):
    """获取当前用户的额度信息（含角色）"""
    clerk_user_id = token_payload.get("sub", "")
    email = token_payload.get("email", "")

    logger.info("[quota] GET /quota: user=%s email=%s", clerk_user_id, email)

    try:
        quota = ensure_user_and_quota(clerk_user_id, email)
        total = quota.get("total_quota", 0)
        used = quota.get("used_quota", 0)
        role = quota.get("role", "user")
        logger.info("[quota] Returning: total=%s used=%s remaining=%s role=%s", total, used, total - used, role)
        return {
            "success": True,
            "total": total,
            "used": used,
            "remaining": total - used,
            "role": role,
        }
    except Exception as e:
        logger.error("[quota] Failed: %s", e, exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"获取额度失败: {str(e)}")


@router.get("/history")
async def get_upload_history(token_payload: dict = Depends(verify_clerk_token)):
    """获取当前用户的解析历史记录"""
    clerk_user_id = token_payload.get("sub", "")
    history = get_history(clerk_user_id)
    return {"success": True, "history": history}


@router.get("/download/{filename:path}")
async def download_file(filename: str):
    """下载生成的 Excel 文件"""
    # 路径遍历防护：只取文件名部分，拒绝包含路径分隔符的请求
    safe_name = os.path.basename(filename)
    if safe_name != filename or "/" in filename or "\\" in filename:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="非法的文件名")
    file_path = OUTPUT_DIR / safe_name
    if not file_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path=str(file_path),
        filename=safe_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
