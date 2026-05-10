"""LLM 引擎模块测试"""

import json
import pytest
from unittest.mock import patch, MagicMock

from backend.core.llm_engine import extract_paper_info, _parse_response, _build_user_prompt


class TestBuildUserPrompt:
    def test_includes_text(self):
        prompt = _build_user_prompt("Test paper content")
        assert "Test paper content" in prompt

    def test_truncates_long_text(self):
        long_text = "a" * 10000
        prompt = _build_user_prompt(long_text)
        assert len(prompt) < 10000


class TestParseResponse:
    def test_valid_json(self):
        raw = '{"question": "test", "method": "m", "metrics": "", "innovation": "", "limitation": ""}'
        result = _parse_response(raw)
        assert result["question"] == "test"

    def test_json_with_extra_text(self):
        raw = 'Here is the result: {"question": "q", "method": "m", "metrics": "", "innovation": "", "limitation": ""} done.'
        result = _parse_response(raw)
        assert result["question"] == "q"

    def test_missing_fields_filled(self):
        raw = '{"question": "q"}'
        result = _parse_response(raw)
        assert result["method"] == ""
        assert result["metrics"] == ""

    def test_invalid_json_raises(self):
        with pytest.raises(Exception, match="JSON 解析失败"):
            _parse_response("no json here")

    def test_malformed_json_raises(self):
        with pytest.raises(Exception, match="JSON 解析失败"):
            _parse_response("{bad json}")

    def test_empty_limitation_gets_fallback(self):
        raw = '{"question": "q", "method": "m", "metrics": "met", "innovation": "i", "limitation": ""}'
        result = _parse_response(raw)
        assert len(result["limitation"]) >= 15

    def test_short_limitation_gets_fallback(self):
        raw = '{"question": "q", "method": "m", "metrics": "met", "innovation": "i", "limitation": "太短"}'
        result = _parse_response(raw)
        assert len(result["limitation"]) >= 15

    def test_good_limitation_preserved(self):
        good = "自注意力机制的计算复杂度与序列长度呈二次关系，处理长序列时计算开销较大，限制了其在超长文档上的应用。"
        raw = json.dumps({"question": "q", "method": "m", "metrics": "met", "innovation": "i", "limitation": good})
        result = _parse_response(raw)
        assert result["limitation"] == good

    def test_limitation_forced_empty_when_core_missing(self):
        """前四项有缺失时，即使 LLM 返回了 limitation 也必须清空"""
        raw = '{"question": "", "method": "m", "metrics": "", "innovation": "i", "limitation": "some limitation text"}'
        result = _parse_response(raw)
        assert result["limitation"] == ""

    def test_limitation_empty_when_all_core_empty(self):
        """前四项全空时，limitation 必须为空"""
        raw = '{"question": "", "method": "", "metrics": "", "innovation": "", "limitation": "should not appear"}'
        result = _parse_response(raw)
        assert result["limitation"] == ""


class TestExtractPaperInfo:
    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine._call_api")
    def test_returns_dict(self, mock_call):
        mock_call.return_value = '{"question": "q", "method": "m", "metrics": "met", "innovation": "i", "limitation": "l"}'
        result = extract_paper_info("some paper text")
        assert result["question"] == "q"
        assert result["method"] == "m"
        mock_call.assert_called_once()

    @patch("backend.core.llm_engine.API_KEY", "")
    def test_no_api_key_raises(self):
        with pytest.raises(Exception, match="DEEPSEEK_API_KEY"):
            extract_paper_info("text")

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine._call_api")
    def test_api_error_propagates(self, mock_call):
        mock_call.side_effect = Exception("API 连接失败")
        with pytest.raises(Exception, match="API 连接失败"):
            extract_paper_info("text")

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine._call_api")
    def test_sends_messages_structure(self, mock_call):
        mock_call.return_value = '{"question": "", "method": "", "metrics": "", "innovation": "", "limitation": ""}'
        extract_paper_info("test text")
        messages = mock_call.call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"       # few-shot example
        assert messages[2]["role"] == "assistant"   # few-shot response
        assert messages[3]["role"] == "user"        # actual input
        assert "test text" in messages[3]["content"]
