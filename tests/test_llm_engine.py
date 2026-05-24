"""LLM 引擎模块测试"""

import json
import pytest
from unittest.mock import patch

from backend.core.llm_engine import (
    extract_paper_info, _parse_response, _strip_code_fences, _build_user_prompt,
    _repair_json, _build_fallback_result, _save_failure_log,
    LLM_KEYS, METADATA_KEYS, ANALYSIS_KEYS,
)


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

    def test_json_wrapped_in_code_fence(self):
        raw = "```json\n" + json.dumps(FULL_LLM_RESULT, ensure_ascii=False) + "\n```"
        result = _parse_response(raw)
        assert result["question"] == "传统 RNN 存在长距离依赖问题"

    def test_json_wrapped_in_plain_code_fence(self):
        raw = "```\n" + json.dumps(FULL_LLM_RESULT, ensure_ascii=False) + "\n```"
        result = _parse_response(raw)
        assert result["author"] == "Vaswani et al."

    def test_json_with_trailing_comma(self):
        raw = '{"question": "test", "author": "test",}'
        result = _parse_response(raw)
        assert result["question"] == "test"
        assert result["author"] == "test"

    def test_code_fence_with_extra_text(self):
        raw = "Here is the extracted info:\n```json\n" + json.dumps(FULL_LLM_RESULT, ensure_ascii=False) + "\n```\nDone."
        result = _parse_response(raw)
        assert result["method"] == "基于多头自注意力机制的 Transformer 架构"


class TestStripCodeFences:
    def test_strips_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_strips_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_returns_stripped_when_no_fence(self):
        text = '  {"key": "value"}  '
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_fence_with_surrounding_text(self):
        text = 'Some explanation\n```json\n{"key": "value"}\n```\nMore text'
        assert _strip_code_fences(text) == '{"key": "value"}'


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


class TestRepairJson:
    def test_repair_trailing_comma(self):
        raw = '{"question": "test", "author": "test",}'
        result = _repair_json(raw)
        assert result is not None
        assert result["question"] == "test"

    def test_repair_single_quotes(self):
        raw = "{'question': 'test', 'author': 'test'}"
        result = _repair_json(raw)
        assert result is not None
        assert result["question"] == "test"

    def test_repair_code_fence(self):
        raw = '```json\n{"question": "test"}\n```'
        result = _repair_json(raw)
        assert result is not None
        assert result["question"] == "test"

    def test_repair_with_extra_text(self):
        raw = 'Here is the result:\n{"question": "test", "method": "m"}\nDone.'
        result = _repair_json(raw)
        assert result is not None
        assert result["question"] == "test"

    def test_repair_no_json_returns_none(self):
        result = _repair_json("no json here at all")
        assert result is None

    def test_repair_broken_json_returns_none(self):
        result = _repair_json("{completely broken +++}")
        assert result is None


class TestBuildFallbackResult:
    def test_returns_all_keys(self):
        result = _build_fallback_result()
        for key in LLM_KEYS:
            assert key in result

    def test_all_fields_are_fallback_value(self):
        result = _build_fallback_result()
        for key in LLM_KEYS:
            if key == "limitation":
                assert len(result[key]) >= 15
            else:
                assert result[key] == "未成功解析"

    def test_limitation_passes_quality_check(self):
        result = _build_fallback_result()
        assert len(result["limitation"]) >= 15


class TestSaveFailureLog:
    def test_creates_log_file(self, tmp_path):
        with patch("backend.core.llm_engine.LOG_DIR", tmp_path):
            _save_failure_log("raw response content", "test.pdf", "parse error")
            logs = list(tmp_path.glob("fail_*.txt"))
            assert len(logs) == 1
            content = logs[0].read_text(encoding="utf-8")
            assert "test.pdf" in content
            assert "parse error" in content
            assert "raw response content" in content


class TestExtractPaperInfoFallback:
    """测试 extract_paper_info 的 3 级降级容错"""

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine._call_api")
    def test_level1_normal_parse(self, mock_call):
        """Level 1: 正常 JSON 直接解析成功"""
        mock_call.return_value = json.dumps(FULL_LLM_RESULT, ensure_ascii=False)
        result = extract_paper_info("text", filename="test.pdf")
        assert result["question"] == FULL_LLM_RESULT["question"]
        assert result["author"] == FULL_LLM_RESULT["author"]

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine._call_api")
    def test_level2_repair_fallback(self, mock_call):
        """Level 2: JSON 有格式错误但可修复"""
        # 尾部逗号 — _parse_response 已处理，但测试 repair 路径
        mock_call.return_value = '{"question": "test question", "author": "test",}'
        result = extract_paper_info("text", filename="bad.pdf")
        assert result["question"] == "test question"

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine.time.sleep")
    @patch("backend.core.llm_engine._call_api")
    def test_level3_fallback_on_no_json(self, mock_call, mock_sleep, tmp_path):
        """Level 3: LLM 返回完全无 JSON，重试后使用降级结果"""
        mock_call.return_value = "I cannot parse this paper. Here is my analysis in plain text."
        with patch("backend.core.llm_engine.LOG_DIR", tmp_path):
            result = extract_paper_info("text", filename="unreadable.pdf")
        assert result["question"] == "未成功解析"
        assert result["method"] == "未成功解析"
        assert len(result["limitation"]) >= 15
        # 1 + 2 retries = 3 calls
        assert mock_call.call_count == 3
        # 2 retries with sleep(1)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(1)
        # 验证日志文件已创建（最后一次重试的）
        logs = list(tmp_path.glob("fail_*.txt"))
        assert len(logs) == 1

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine.time.sleep")
    @patch("backend.core.llm_engine._call_api")
    def test_level3_fallback_on_malformed_json(self, mock_call, mock_sleep, tmp_path):
        """Level 3: JSON 格式严重损坏，重试后使用降级结果"""
        mock_call.return_value = "{broken json +++ unclosed"
        with patch("backend.core.llm_engine.LOG_DIR", tmp_path):
            result = extract_paper_info("text", filename="corrupt.pdf")
        assert result["question"] == "未成功解析"
        assert mock_call.call_count == 3

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine._call_api")
    def test_api_error_still_raises(self, mock_call):
        """API 网络错误仍然应抛出异常（非 JSON 解析问题）"""
        mock_call.side_effect = Exception("API 连接失败")
        with pytest.raises(Exception, match="API 连接失败"):
            extract_paper_info("text", filename="network.pdf")

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine.time.sleep")
    @patch("backend.core.llm_engine._call_api")
    def test_retry_succeeds_on_second_attempt(self, mock_call, mock_sleep):
        """重试成功：第一次返回无效 JSON，第二次返回有效 JSON"""
        mock_call.side_effect = [
            "invalid json response",
            json.dumps(FULL_LLM_RESULT, ensure_ascii=False),
        ]
        result = extract_paper_info("text", filename="retry.pdf")
        assert result["question"] == FULL_LLM_RESULT["question"]
        assert mock_call.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine.time.sleep")
    @patch("backend.core.llm_engine._call_api")
    def test_retry_succeeds_on_third_attempt(self, mock_call, mock_sleep):
        """重试成功：前两次失败，第三次返回有效 JSON"""
        mock_call.side_effect = [
            "bad response 1",
            "bad response 2",
            json.dumps(FULL_LLM_RESULT, ensure_ascii=False),
        ]
        result = extract_paper_info("text", filename="retry3.pdf")
        assert result["question"] == FULL_LLM_RESULT["question"]
        assert mock_call.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine.time.sleep")
    @patch("backend.core.llm_engine._call_api")
    def test_no_retry_when_level1_succeeds(self, mock_call, mock_sleep):
        """Level 1 直接成功时不重试"""
        mock_call.return_value = json.dumps(FULL_LLM_RESULT, ensure_ascii=False)
        result = extract_paper_info("text", filename="good.pdf")
        assert result["question"] == FULL_LLM_RESULT["question"]
        assert mock_call.call_count == 1
        mock_sleep.assert_not_called()

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine.time.sleep")
    @patch("backend.core.llm_engine._call_api")
    def test_no_retry_when_level2_succeeds(self, mock_call, mock_sleep):
        """Level 2 修复成功时不重试"""
        mock_call.return_value = '{"question": "q", "author": "a",}'
        result = extract_paper_info("text", filename="repair.pdf")
        assert result["question"] == "q"
        assert mock_call.call_count == 1
        mock_sleep.assert_not_called()

    @patch("backend.core.llm_engine.API_KEY", "test-key")
    @patch("backend.core.llm_engine.time.sleep")
    @patch("backend.core.llm_engine._call_api")
    def test_api_error_no_retry(self, mock_call, mock_sleep):
        """API 网络错误不重试（只重试 JSON 解析失败）"""
        mock_call.side_effect = Exception("API 连接失败")
        with pytest.raises(Exception, match="API 连接失败"):
            extract_paper_info("text", filename="net.pdf")
        assert mock_call.call_count == 1
        mock_sleep.assert_not_called()
