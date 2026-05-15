"""LLM 引擎模块测试"""

import json
import pytest
from unittest.mock import patch

from backend.core.llm_engine import extract_paper_info, _parse_response, _build_user_prompt, LLM_KEYS, METADATA_KEYS, ANALYSIS_KEYS


# === 完整的 mock LLM 返回值（20 个字段） ===
FULL_LLM_RESULT = {
    "author": "Vaswani et al.",
    "year": "2017",
    "journal": "NeurIPS",
    "doi": "10.48550/arXiv.1706.03762",
    "keywords": "attention, transformer",
    "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
    "question": "传统 RNN 存在长距离依赖问题",
    "background": "序列到序列模型主要依赖 RNN 及其变体",
    "gap": "RNN 无法并行化训练且梯度消失严重",
    "objective": "提出纯注意力模型替代循环结构",
    "method": "基于多头自注意力机制的 Transformer 架构",
    "dataset": "WMT14 英德翻译数据集（450万句对）",
    "metrics": "WMT14 英德翻译 41.0 BLEU，超越 SOTA 2 个点",
    "comparison": "与基于 LSTM 的编码器-解码器模型对比",
    "innovation": "首次完全依赖注意力机制实现并行化训练",
    "findings": "消融实验表明多头注意力对性能至关重要",
    "conclusion": "纯注意力模型在翻译任务上超越了 RNN",
    "limitation": "自注意力计算复杂度与序列长度呈二次关系，处理长序列开销大",
    "future_work": "探索更高效的注意力机制以处理更长序列",
    "inspiration": "纯注意力架构的设计思路可迁移到各类序列建模任务",
}


class TestBuildUserPrompt:
    def test_includes_text(self):
        prompt = _build_user_prompt("Test paper content")
        assert "Test paper content" in prompt

    def test_truncates_long_text(self):
        long_text = "a" * 20000
        prompt = _build_user_prompt(long_text)
        assert len(prompt) < 20000


class TestParseResponse:
    def test_valid_json(self):
        raw = json.dumps(FULL_LLM_RESULT, ensure_ascii=False)
        result = _parse_response(raw)
        assert result["question"] == "传统 RNN 存在长距离依赖问题"
        assert result["author"] == "Vaswani et al."

    def test_json_with_extra_text(self):
        raw = "Here is the result: " + json.dumps(FULL_LLM_RESULT, ensure_ascii=False) + " done."
        result = _parse_response(raw)
        assert result["question"] == "传统 RNN 存在长距离依赖问题"

    def test_missing_fields_filled(self):
        raw = '{"question": "q"}'
        result = _parse_response(raw)
        for key in LLM_KEYS:
            assert key in result
        # 缺失字段应为 "未明确提及"
        assert result["author"] == "未明确提及"
        assert result["year"] == "未明确提及"

    def test_invalid_json_raises(self):
        with pytest.raises(Exception, match="JSON 解析失败"):
            _parse_response("no json here")

    def test_malformed_json_raises(self):
        with pytest.raises(Exception, match="JSON 解析失败"):
            _parse_response("{bad json}")

    def test_empty_limitation_gets_fallback(self):
        result_data = dict(FULL_LLM_RESULT)
        result_data["limitation"] = ""
        raw = json.dumps(result_data, ensure_ascii=False)
        result = _parse_response(raw)
        assert len(result["limitation"]) >= 15

    def test_short_limitation_gets_fallback(self):
        result_data = dict(FULL_LLM_RESULT)
        result_data["limitation"] = "太短"
        raw = json.dumps(result_data, ensure_ascii=False)
        result = _parse_response(raw)
        assert len(result["limitation"]) >= 15

    def test_good_limitation_preserved(self):
        good = "自注意力机制的计算复杂度与序列长度呈二次关系，处理长序列时计算开销较大，限制了其在超长文档上的应用。"
        result_data = dict(FULL_LLM_RESULT)
        result_data["limitation"] = good
        raw = json.dumps(result_data, ensure_ascii=False)
        result = _parse_response(raw)
        assert result["limitation"] == good

    def test_empty_analysis_fields_get_default(self):
        result_data = dict(FULL_LLM_RESULT)
        result_data["question"] = ""
        result_data["findings"] = ""
        raw = json.dumps(result_data, ensure_ascii=False)
        result = _parse_response(raw)
        assert result["question"] == "未明确提及"
        assert result["findings"] == "未明确提及"

    def test_empty_metadata_fields_get_default(self):
        result_data = dict(FULL_LLM_RESULT)
        result_data["author"] = ""
        result_data["journal"] = ""
        raw = json.dumps(result_data, ensure_ascii=False)
        result = _parse_response(raw)
        assert result["author"] == "未明确提及"
        assert result["journal"] == "未明确提及"

    def test_all_keys_present_in_output(self):
        raw = json.dumps(FULL_LLM_RESULT, ensure_ascii=False)
        result = _parse_response(raw)
        for key in LLM_KEYS:
            assert key in result, f"Missing key: {key}"


class TestExtractPaperInfo:
    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine._call_api")
    def test_returns_dict(self, mock_call):
        mock_call.return_value = json.dumps(FULL_LLM_RESULT, ensure_ascii=False)
        result = extract_paper_info("some paper text")
        assert result["question"] == FULL_LLM_RESULT["question"]
        assert result["author"] == FULL_LLM_RESULT["author"]
        assert result["method"] == FULL_LLM_RESULT["method"]
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
        mock_call.return_value = json.dumps(FULL_LLM_RESULT, ensure_ascii=False)
        extract_paper_info("test text")
        messages = mock_call.call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"       # few-shot example
        assert messages[2]["role"] == "assistant"   # few-shot response
        assert messages[3]["role"] == "user"        # actual input
        assert "test text" in messages[3]["content"]
