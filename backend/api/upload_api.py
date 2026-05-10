"""PDF 上传 + 处理 + 导出接口（SSE 进度推送）"""

import json
import os
from pathlib import Path

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse

import fitz  # PyMuPDF

from backend.core.pdf_parser import extract_text
from backend.core.llm_engine import extract_paper_info
from backend.core.excel_writer import write_excel

router = APIRouter()

# 目录配置
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# 限制常量
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_PAGES = 30
MAX_FILES = 20


def _sse_event(event: str, data: dict) -> str:
    """格式化一条 SSE 消息"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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
    """处理单个 PDF：解析 → LLM 提取 → 返回结构化数据"""
    text = extract_text(str(filepath))
    info = extract_paper_info(text)
    info["title"] = filename.replace(".pdf", "").replace("_", " ")
    return info


@router.post("/upload")
async def upload_pdfs(files: list[UploadFile] = File(...)):
    """批量上传 PDF → 解析 → LLM 提取 → 生成 Excel（SSE 进度推送）"""

    async def event_stream():
        # === 文件数量校验 ===
        if len(files) > MAX_FILES:
            yield _sse_event("error", {"message": f"最多上传 {MAX_FILES} 个文件"})
            yield _sse_event("done", {"success": False, "download_url": "", "results": [], "errors": [f"最多上传 {MAX_FILES} 个文件"]})
            return

        # === 阶段 1：校验并保存文件 ===
        yield _sse_event("progress", {"step": "upload", "percent": 10, "message": "上传文件"})

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
            yield _sse_event("error", {"message": "所有文件校验失败：\n" + "\n".join(errors)})
            yield _sse_event("done", {"success": False, "download_url": "", "results": [], "errors": errors})
            return

        # === 阶段 2：逐个处理 PDF ===
        results: list[dict] = []
        process_errors: list[str] = []
        total = len(saved_files)

        for idx, filename in enumerate(saved_files):
            # 解析 PDF
            yield _sse_event("progress", {"step": "parse", "percent": 20, "message": f"解析 PDF ({idx + 1}/{total})"})

            # LLM 提取
            llm_percent = 40 + int(40 * idx / total)
            yield _sse_event("progress", {"step": "llm", "percent": llm_percent, "message": f"调用 LLM 提取信息 ({idx + 1}/{total})"})

            filepath = UPLOAD_DIR / filename
            try:
                result = _process_single_pdf(filepath, filename)
                results.append(result)
                yield _sse_event("file_done", {"filename": filename, "index": idx, "total": total})
            except Exception as e:
                process_errors.append(f"处理 {filename} 失败: {str(e)}")
                yield _sse_event("error", {"message": f"处理 {filename} 失败: {str(e)}"})

        if not results:
            yield _sse_event("error", {"message": "所有文件处理失败：\n" + "\n".join(process_errors)})
            yield _sse_event("done", {"success": False, "download_url": "", "results": [], "errors": errors + process_errors})
            return

        # === 阶段 3：写入 Excel ===
        yield _sse_event("progress", {"step": "export", "percent": 90, "message": "生成 Excel"})

        output_filename = "literature_matrix.xlsx"
        output_path = OUTPUT_DIR / output_filename
        write_excel(results, str(output_path))

        # === 完成 ===
        yield _sse_event("progress", {"step": "done", "percent": 100, "message": "完成下载"})
        yield _sse_event("done", {
            "success": True,
            "download_url": f"/download/{output_filename}",
            "results": results,
            "errors": errors + process_errors,
        })

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/download/{filename}")
async def download_file(filename: str):
    """下载生成的 Excel 文件"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
