"""PDF 上传接口测试"""

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
        data = resp.json()
        assert data["success"] is True
        assert len(data["results"]) == 1
        assert data["download_url"] is not None
        result = data["results"][0]
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
        data = resp.json()
        assert data["success"] is False
        assert any("不是 PDF" in e for e in data["errors"])

    def test_too_many_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"file{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(21)
        ]
        resp = client.post("/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert any("最多" in e for e in data["errors"])

    def test_oversized_file_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        big_bytes = b"%PDF-1.0" + b"x" * (11 * 1024 * 1024)
        resp = client.post(
            "/upload",
            files=[("files", ("big.pdf", big_bytes, "application/pdf"))],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert any("10MB" in e for e in data["errors"])

    def test_too_many_pages_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(31)
        resp = client.post(
            "/upload",
            files=[("files", ("long.pdf", pdf_bytes, "application/pdf"))],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert any("long.pdf" in e for e in data["errors"])

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
        data = resp.json()
        assert data["success"] is True
        assert len(data["results"]) == 3

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
        data = resp.json()
        assert data["success"] is False
        assert any("LLM failed" in e for e in data["errors"])

    @patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM_RESULT)
    def test_json_content_type(self, mock_llm, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        resp = client.post(
            "/upload",
            files=[("files", ("test.pdf", pdf_bytes, "application/pdf"))],
        )
        assert "application/json" in resp.headers["content-type"]


FALLBACK_LLM_RESULT = {
    key: "未成功解析" for key in MOCK_LLM_RESULT
}
FALLBACK_LLM_RESULT["limitation"] = (
    "论文未明确讨论局限性，潜在问题可能包括："
    "泛化能力有限、计算开销较大、缺乏真实场景部署验证。"
)


class TestFallbackBehavior:
    """测试降级模式下的行为"""

    @patch("backend.api.upload_api.extract_paper_info", return_value=FALLBACK_LLM_RESULT)
    def test_fallback_result_still_exports_excel(self, mock_llm, tmp_path, monkeypatch):
        """降级结果仍然能导出 Excel，不崩溃"""
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        resp = client.post(
            "/upload",
            files=[("files", ("test.pdf", pdf_bytes, "application/pdf"))],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["results"]) == 1
        assert data["results"][0]["question"] == "未成功解析"
        assert data["download_url"] is not None

    @patch("backend.api.upload_api.extract_paper_info", return_value=FALLBACK_LLM_RESULT)
    def test_fallback_populates_warnings(self, mock_llm, tmp_path, monkeypatch):
        """降级模式在 warnings 字段中报告"""
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        resp = client.post(
            "/upload",
            files=[("files", ("bad.pdf", pdf_bytes, "application/pdf"))],
        )
        data = resp.json()
        assert data["success"] is True
        assert len(data["warnings"]) == 1
        assert "降级模式" in data["warnings"][0]
        assert len(data["errors"]) == 0

    @patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM_RESULT)
    def test_normal_result_no_warnings(self, mock_llm, tmp_path, monkeypatch):
        """正常结果没有 warnings"""
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        pdf_bytes = _make_pdf_bytes(1)
        resp = client.post(
            "/upload",
            files=[("files", ("good.pdf", pdf_bytes, "application/pdf"))],
        )
        data = resp.json()
        assert data["success"] is True
        assert len(data.get("warnings", [])) == 0


class TestDownload:
    def test_download_nonexistent(self):
        resp = client.get("/download/nonexistent.xlsx")
        assert resp.status_code == 404


class TestAdminBypass:
    """管理员绕过额度限制测试"""

    @patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM_RESULT)
    def test_admin_unlimited_upload(self, mock_llm, tmp_path, monkeypatch):
        """管理员可以无限上传，不扣减额度"""
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.get_user_role", lambda email: "admin")
        monkeypatch.setattr(
            "backend.api.upload_api.ensure_user_and_quota",
            lambda uid, email: {"total_quota": 999999, "used_quota": 0, "role": "admin"},
        )
        monkeypatch.setattr("backend.api.upload_api.get_remaining_quota", lambda uid, email="": 999999)

        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"paper{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(3)
        ]
        resp = client.post("/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["results"]) == 3

    @patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM_RESULT)
    def test_admin_no_quota_deduction(self, mock_llm, tmp_path, monkeypatch):
        """管理员上传后不扣减额度"""
        deduct_called = {"called": False}

        def mock_deduct_batch(uid, count, email=""):
            deduct_called["called"] = True
            return True, 999999

        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.get_user_role", lambda email: "admin")
        monkeypatch.setattr(
            "backend.api.upload_api.ensure_user_and_quota",
            lambda uid, email: {"total_quota": 999999, "used_quota": 0, "role": "admin"},
        )
        monkeypatch.setattr("backend.api.upload_api.get_remaining_quota", lambda uid, email="": 999999)
        monkeypatch.setattr("backend.api.upload_api.deduct_quota_batch", mock_deduct_batch)

        pdf_bytes = _make_pdf_bytes(1)
        resp = client.post(
            "/upload",
            files=[("files", ("test.pdf", pdf_bytes, "application/pdf"))],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        # Admin should NOT trigger deduction
        assert deduct_called["called"] is False


class TestInsufficientQuota:
    """额度不足阻止上传测试"""

    def test_upload_blocked_when_files_exceed_quota(self, tmp_path, monkeypatch):
        """文件数量超过剩余额度时阻止上传"""
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.get_remaining_quota", lambda uid, email="": 1)

        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"paper{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(3)
        ]
        resp = client.post("/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert any("额度不足" in e for e in data["errors"])

    def test_upload_allowed_when_quota_sufficient(self, tmp_path, monkeypatch):
        """文件数量不超过剩余额度时允许上传"""
        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.get_remaining_quota", lambda uid, email="": 5)

        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"paper{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(3)
        ]
        resp = client.post("/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


class TestBatchDeduction:
    """按成功文件数扣减额度测试"""

    @patch("backend.api.upload_api.extract_paper_info", return_value=MOCK_LLM_RESULT)
    def test_deduct_by_success_count(self, mock_llm, tmp_path, monkeypatch):
        """扣减数量等于成功处理的文件数"""
        deducted = {"count": 0}

        def mock_deduct_batch(uid, count, email=""):
            deducted["count"] = count
            return True, 3 - count

        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.deduct_quota_batch", mock_deduct_batch)

        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"paper{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(3)
        ]
        resp = client.post("/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        # All 3 files succeeded, so deduct 3
        assert deducted["count"] == 3

    @patch("backend.api.upload_api.extract_paper_info", side_effect=Exception("LLM failed"))
    def test_no_deduction_when_all_fail(self, mock_llm, tmp_path, monkeypatch):
        """所有文件失败时不扣减额度"""
        deducted = {"called": False}

        def mock_deduct_batch(uid, count, email=""):
            deducted["called"] = True
            deducted["count"] = count
            return True, 3

        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.deduct_quota_batch", mock_deduct_batch)

        pdf_bytes = _make_pdf_bytes(1)
        resp = client.post(
            "/upload",
            files=[("files", ("test.pdf", pdf_bytes, "application/pdf"))],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        # No successful files, so no deduction
        assert deducted["called"] is False


class TestMixedBatchDeduction:
    """混合批次（成功+失败）只扣减成功论文额度"""

    def test_only_success_count_deducted(self, tmp_path, monkeypatch):
        """1 成功 + 1 fallback → 只扣 1"""
        call_count = {"n": 0}
        deducted = {"count": 0}

        def mock_extract(text, filename=""):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return dict(MOCK_LLM_RESULT)
            return dict(FALLBACK_LLM_RESULT)

        def mock_deduct_batch(uid, count, email=""):
            deducted["count"] = count
            return True, 10

        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.extract_paper_info", mock_extract)
        monkeypatch.setattr("backend.api.upload_api.deduct_quota_batch", mock_deduct_batch)

        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", ("good.pdf", pdf_bytes, "application/pdf")),
            ("files", ("bad.pdf", pdf_bytes, "application/pdf")),
        ]
        resp = client.post("/upload", files=files)
        data = resp.json()
        assert data["success"] is True
        assert len(data["results"]) == 2
        assert len(data["warnings"]) == 1
        assert deducted["count"] == 1

    def test_all_fallback_no_deduction(self, tmp_path, monkeypatch):
        """全部 fallback → 扣 0"""
        deducted = {"called": False}

        def mock_deduct_batch(uid, count, email=""):
            deducted["called"] = True
            deducted["count"] = count
            return True, 10

        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.extract_paper_info", lambda t, filename="": dict(FALLBACK_LLM_RESULT))
        monkeypatch.setattr("backend.api.upload_api.deduct_quota_batch", mock_deduct_batch)

        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"bad{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(3)
        ]
        resp = client.post("/upload", files=files)
        data = resp.json()
        assert data["success"] is True
        assert len(data["results"]) == 3
        assert len(data["warnings"]) == 3
        assert deducted["called"] is False


class TestBatchStress:
    """批量上传压力测试：验证不同批次大小下 quota 扣减正确"""

    @staticmethod
    def _make_mixed_extract(success_ratio: float):
        """返回一个 mock extract 函数，按比例返回成功/fallback 结果"""
        call_count = {"n": 0}

        def extract(text, filename=""):
            call_count["n"] += 1
            if call_count["n"] <= int(1 / success_ratio) * call_count["n"] * success_ratio:
                return dict(MOCK_LLM_RESULT)
            return dict(FALLBACK_LLM_RESULT)

        # Simpler approach: alternate success/fallback based on index
        def extract_alternating(text, filename=""):
            call_count["n"] += 1
            if call_count["n"] % 2 == 1:
                return dict(MOCK_LLM_RESULT)
            return dict(FALLBACK_LLM_RESULT)

        return extract_alternating, call_count

    def _run_batch_test(self, n_files, tmp_path, monkeypatch):
        """通用批量测试：上传 n_files 个文件，返回 (response_data, deducted_count)"""
        extracted = {"n": 0}
        deducted = {"count": 0}

        def mock_extract(text, filename=""):
            extracted["n"] += 1
            if extracted["n"] % 2 == 1:
                return dict(MOCK_LLM_RESULT)
            return dict(FALLBACK_LLM_RESULT)

        def mock_deduct_batch(uid, count, email=""):
            deducted["count"] = count
            return True, 999

        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.extract_paper_info", mock_extract)
        monkeypatch.setattr("backend.api.upload_api.deduct_quota_batch", mock_deduct_batch)
        monkeypatch.setattr("backend.api.upload_api.get_remaining_quota", lambda uid, email="": 999)
        monkeypatch.setattr(
            "backend.api.upload_api.ensure_user_and_quota",
            lambda uid, email: {"total_quota": 999, "used_quota": 0, "role": "user"},
        )

        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"paper{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(n_files)
        ]
        resp = client.post("/upload", files=files)
        return resp.json(), deducted["count"]

    def test_batch_2_files(self, tmp_path, monkeypatch):
        """2 篇：1 成功 + 1 fallback → 扣 1"""
        data, deducted = self._run_batch_test(2, tmp_path, monkeypatch)
        assert data["success"] is True
        assert len(data["results"]) == 2
        assert deducted == 1
        assert len(data["warnings"]) == 1

    def test_batch_5_files(self, tmp_path, monkeypatch):
        """5 篇：3 成功 + 2 fallback → 扣 3"""
        data, deducted = self._run_batch_test(5, tmp_path, monkeypatch)
        assert data["success"] is True
        assert len(data["results"]) == 5
        assert deducted == 3
        assert len(data["warnings"]) == 2

    def test_batch_10_files(self, tmp_path, monkeypatch):
        """10 篇：5 成功 + 5 fallback → 扣 5"""
        data, deducted = self._run_batch_test(10, tmp_path, monkeypatch)
        assert data["success"] is True
        assert len(data["results"]) == 10
        assert deducted == 5
        assert len(data["warnings"]) == 5

    def test_batch_20_files(self, tmp_path, monkeypatch):
        """20 篇：10 成功 + 10 fallback → 扣 10"""
        data, deducted = self._run_batch_test(20, tmp_path, monkeypatch)
        assert data["success"] is True
        assert len(data["results"]) == 20
        assert deducted == 10
        assert len(data["warnings"]) == 10

    def test_batch_20_all_success(self, tmp_path, monkeypatch):
        """20 篇全部成功 → 扣 20"""
        extracted = {"n": 0}
        deducted = {"count": 0}

        def mock_extract(text, filename=""):
            extracted["n"] += 1
            return dict(MOCK_LLM_RESULT)

        def mock_deduct_batch(uid, count, email=""):
            deducted["count"] = count
            return True, 999

        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.extract_paper_info", mock_extract)
        monkeypatch.setattr("backend.api.upload_api.deduct_quota_batch", mock_deduct_batch)
        monkeypatch.setattr("backend.api.upload_api.get_remaining_quota", lambda uid, email="": 999)
        monkeypatch.setattr(
            "backend.api.upload_api.ensure_user_and_quota",
            lambda uid, email: {"total_quota": 999, "used_quota": 0, "role": "user"},
        )

        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"paper{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(20)
        ]
        resp = client.post("/upload", files=files)
        data = resp.json()
        assert data["success"] is True
        assert len(data["results"]) == 20
        assert deducted["count"] == 20
        assert len(data["warnings"]) == 0

    def test_batch_20_all_fallback(self, tmp_path, monkeypatch):
        """20 篇全部 fallback → 扣 0"""
        deducted = {"count": -1}

        def mock_extract(text, filename=""):
            return dict(FALLBACK_LLM_RESULT)

        def mock_deduct_batch(uid, count, email=""):
            deducted["count"] = count
            return True, 999

        monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.OUTPUT_DIR", tmp_path)
        monkeypatch.setattr("backend.api.upload_api.extract_paper_info", mock_extract)
        monkeypatch.setattr("backend.api.upload_api.deduct_quota_batch", mock_deduct_batch)
        monkeypatch.setattr("backend.api.upload_api.get_remaining_quota", lambda uid, email="": 999)
        monkeypatch.setattr(
            "backend.api.upload_api.ensure_user_and_quota",
            lambda uid, email: {"total_quota": 999, "used_quota": 0, "role": "user"},
        )

        pdf_bytes = _make_pdf_bytes(1)
        files = [
            ("files", (f"paper{i}.pdf", pdf_bytes, "application/pdf"))
            for i in range(20)
        ]
        resp = client.post("/upload", files=files)
        data = resp.json()
        assert data["success"] is True
        assert len(data["results"]) == 20
        # success_count == 0, so deduct_quota_batch is never called
        assert deducted["count"] == -1
        assert len(data["warnings"]) == 20


class TestQuotaEndpoint:
    """额度接口返回角色信息测试"""

    def test_quota_returns_role_field(self):
        """GET /quota 响应包含 role 字段"""
        resp = client.get("/quota")
        assert resp.status_code == 200
        data = resp.json()
        assert "role" in data
        assert data["role"] == "user"

    def test_admin_quota_returns_admin_role(self, monkeypatch):
        """管理员额度接口返回 admin 角色和无限额度"""
        monkeypatch.setattr(
            "backend.api.upload_api.ensure_user_and_quota",
            lambda uid, email: {"total_quota": 999999, "used_quota": 0, "role": "admin"},
        )
        resp = client.get("/quota")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"
        assert data["remaining"] == 999999
