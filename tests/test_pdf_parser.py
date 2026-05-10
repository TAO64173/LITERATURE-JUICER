"""PDF 解析模块测试"""

import pytest
from pathlib import Path

from backend.core.pdf_parser import extract_text, _is_reference_page, _clean_text


class TestCleanText:
    def test_removes_empty_lines(self):
        assert _clean_text("hello\n\n\nworld") == "hello\nworld"

    def test_removes_short_lines(self):
        text = "This is a valid line\nab\nAnother valid line"
        result = _clean_text(text)
        assert "ab" not in result
        assert "This is a valid line" in result

    def test_strips_whitespace(self):
        assert _clean_text("  hello world  ") == "hello world"


class TestIsReferencePage:
    def test_detects_references(self):
        assert _is_reference_page("References\n[1] Smith et al.") is True

    def test_detects_references_cn(self):
        assert _is_reference_page("参考文献\n[1] 张三") is True

    def test_rejects_normal_page(self):
        assert _is_reference_page("This paper proposes a new method.") is False


class TestExtractText:
    def test_basic_extraction(self, tmp_path):
        doc = __import__("fitz").open()
        doc.new_page().insert_text((72, 72), "Hello World " * 10)
        pdf_path = tmp_path / "test.pdf"
        doc.save(str(pdf_path))
        doc.close()

        result = extract_text(str(pdf_path))
        assert "Hello World" in result

    def test_skips_reference_page(self, tmp_path):
        fitz = __import__("fitz")
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), "Abstract content " * 10)
        doc.new_page().insert_text((72, 72), "References\n[1] Some paper " * 5)
        pdf_path = tmp_path / "test.pdf"
        doc.save(str(pdf_path))
        doc.close()

        result = extract_text(str(pdf_path))
        assert "Abstract content" in result
        # References page should be skipped
        assert "[1] Some paper" not in result

    def test_nonexistent_file_raises(self, tmp_path):
        with pytest.raises((FileNotFoundError, Exception)):
            extract_text(str(tmp_path / "nonexistent.pdf"))
