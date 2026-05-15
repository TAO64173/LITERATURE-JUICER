"""PDF 上传接口测试（SSE 格式）"""

import io
import json
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from unittest.mock import patch

from backend.main import app


client = TestClient(app)


def _make_pdf_bytes(pages: int = 1) -> bytes:
    """生成指定页数的最小 PDF 字节"""
    try:
        import fitz

        doc = fitz.open()
        for _ in range(pages):
            doc.new_page()
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes
    except ImportError:
        return b"%PDF-1.0\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"


def _parse_sse_events(text: str) -> list[dict]:
    """解析 SSE 响应文本为事件列表 [{event, data}, ...]"""
    events = []
    for part in text.split("\n\n"):
        part = part.strip()
        if not part:
            continue
        event_name = "message"
        data_str = ""
        for line in part.split("\n"):
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data_str = line[6:]
        if data_str:
            try:
                events.append({"event": event_name, "data": json.loads(data_str)})
            except json.JSONDecodeError:
                pass
    return events


def _find_event(events: list[dict], name: str) -> dict | None:
    """在事件列表中查找指定名称的事件"""
    for e in events:
        if e["event"] == name:
            return e["data"]
    return None


MOCK_LLM_RESULT = {
    "author": "Test Author et al.",
    "year": "2024",
    "journal": "Test Conference",
    "doi": "10.1234/test.2024",
    "keywords": "test, keyword",
    "abstract": "This is a test abstract for the paper.",
    "question": "test question about research",
    "background": "test background information for the study",
    "gap": "test research gap that needs addressing",
    "objective": "test objective for the study",
    "method": "test method for solving the problem",
    "dataset": "test dataset with 10000 samples",
    "metrics": "test metrics with numbers",
    "comparison": "test comparison with baseline methods",
    "innovation": "test innovation contribution",
    "findings": "test key findings from experiments",
    "conclusion": "test conclusion of the paper",
    "limitation": "test limitation that is long enough to pass validation",
    "future_work": "test future work direction",
    "inspiration": "test inspiration for other researchers",
}


class TestUploadPDFs:
    @patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM_RESULT)
    def test_single_file_upload(self, mock_llm, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        resp = client.post(
            "/upload",
            files=[("files", ("test.pdf", pdf_bytes, "application/pdf"))],
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        done = _find_event(events, "done")
        assert done is not None
        assert done["success"] is True
        assert "test.pdf" in done.get("files", []) or len(done.get("results", [])) == 1
        assert done["download_url"] is not None
        assert len(done["results"]) == 1
        # 验证新字段存在
        result = done["results"][0]
        assert result["author"] == "Test Author et al."
        assert result["year"] == "2024"
        assert result["journal"] == "Test Conference"

    def test_non_pdf_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        resp = client.post(
            "/upload",
            files=[("files", ("test.txt", b"hello", "text/plain"))],
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        error = _find_event(events, "error")
        assert error is not None
        assert "不是 PDF" in error["message"]
        done = _find_event(events, "done")
        assert done["success"] is False

    def test_too_many_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"file{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(21)
        ]
        resp = client.post("/upload", files=files)
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        error = _find_event(events, "error")
        assert error is not None
        assert "最多" in error["message"]

    def test_oversized_file_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        big_bytes = b"%PDF-1.0" + b"x" * (11 * 1024 * 1024)
        resp = client.post(
            "/upload",
            files=[("files", ("big.pdf", big_bytes, "application/pdf"))],
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        error = _find_event(events, "error")
        assert error is not None
        assert "10MB" in error["message"]

    def test_too_many_pages_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(31)
        resp = client.post(
            "/upload",
            files=[("files", ("long.pdf", pdf_bytes, "application/pdf"))],
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        error = _find_event(events, "error")
        assert error is not None
        assert "long.pdf" in error["message"]

    def test_empty_upload(self):
        resp = client.post("/upload", files=[])
        assert resp.status_code == 422

    @patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM_RESULT)
    def test_multi_file_upload(self, mock_llm, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"paper{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(3)
        ]
        resp = client.post("/upload", files=files)
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        done = _find_event(events, "done")
        assert done["success"] is True
        assert len(done["results"]) == 3

    @patch("backend.api.upload_api.extract_paper_info", side_effect=Exception("LLM failed"))
    def test_llm_failure_handled(self, mock_llm, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        resp = client.post(
            "/upload",
            files=[("files", ("test.pdf", pdf_bytes, "application/pdf"))],
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        error = _find_event(events, "error")
        assert error is not None
        assert "LLM failed" in error["message"]
        done = _find_event(events, "done")
        assert done["success"] is False

    @patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM_RESULT)
    def test_sse_content_type(self, mock_llm, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        resp = client.post(
            "/upload",
            files=[("files", ("test.pdf", pdf_bytes, "application/pdf"))],
        )
        assert "text/event-stream" in resp.headers["content-type"]

    @patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM_RESULT)
    def test_progress_events_present(self, mock_llm, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        resp = client.post(
            "/upload",
            files=[("files", ("test.pdf", pdf_bytes, "application/pdf"))],
        )
        events = _parse_sse_events(resp.text)
        progress_events = [e for e in events if e["event"] == "progress"]
        assert len(progress_events) >= 2

    @patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM_RESULT)
    def test_file_done_events(self, mock_llm, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"paper{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(3)
        ]
        resp = client.post("/upload", files=files)
        events = _parse_sse_events(resp.text)
        file_done_events = [e for e in events if e["event"] == "file_done"]
        assert len(file_done_events) == 3


class TestDownload:
    def test_download_nonexistent(self):
        resp = client.get("/download/nonexistent.xlsx")
        assert resp.status_code == 404
