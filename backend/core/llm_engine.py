"""DeepSeek API 调用模块，用于论文信息抽取"""

import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

# === 配置加载 ===
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# 重试配置
MAX_RETRIES = 3
TIMEOUT = 60
BACKOFF_BASE = 1  # 秒


# === Prompt 构建 ===
SYSTEM_PROMPT = """你是一个顶级科研助手，擅长快速阅读机器学习、人工智能、机器人、自动驾驶、NLP、CV 等领域论文。

你的任务不是简单摘抄，而是像 researcher 一样理解论文并总结核心信息。所有输出必须使用中文。

【严格阅读与提取顺序】
你必须按照以下顺序阅读论文并依次提取，前一项未完成不得进入下一项：

第一步：阅读 title + abstract → 提取「研究问题」
第二步：阅读 introduction + method → 提取「研究方法」
第三步：阅读 experiments/results → 提取「实验指标」
第四步：综合全文 → 提取「创新点」
第五步：仅当前四项都已成功提取后 → 阅读 discussion/conclusion/future work → 提取「局限性」

输出 JSON：

{
  "question": "",
  "method": "",
  "metrics": "",
  "innovation": "",
  "limitation": ""
}

【字段要求】

question（研究问题）：
- 论文解决什么问题
- 用中文简洁表达，1句话

method（研究方法）：
- 核心方法、模型、框架
- 用中文概括，1~2句话

metrics（实验指标）：
- 最重要的实验结果
- 包含关键指标或数字（如 accuracy、F1、BLEU、提升幅度等）
- 用中文总结

innovation（创新点）：
- 相比已有工作的新贡献
- 用中文总结，1句话

limitation（局限性）：
- 只有前四项都成功提取后才允许填写此项
- 用中文表达
- 优先从论文的 limitation、discussion、future work、conclusion 中提取
- 如果论文未明确说明，则结合论文内容合理总结
- 如果前四项有任何为空，此项必须为空字符串
- 长度不少于15个字

【输出规则】
1. 仅输出 JSON object
2. 不输出 markdown
3. 不输出解释
4. 不输出 ```json
5. 所有字段使用中文
6. 字段缺失时尽量从论文推断，无法推断则返回空字符串
7. limitation 受前四项约束，前四项不完整时 limitation 必须为空"""

USER_PROMPT_TEMPLATE = """请仔细阅读以下论文内容，按以下优先级顺序提取核心信息（全部用中文）：

提取顺序（必须严格遵守）：
1. 研究问题（question）—— 论文要解决什么问题？
2. 研究方法（method）—— 用了什么方法/模型/框架？
3. 实验指标（metrics）—— 关键实验结果和数据？
4. 创新点（innovation）—— 相比已有工作有什么新贡献？
5. 局限性（limitation）—— 仅当前4项都完成后才提取

论文内容：
{text}

严格只输出 JSON object，不要 markdown，不要解释。"""

FEWSHOT_EXAMPLE = {
    "user": "请提取以下论文信息：Transformer: Attention Is All You Need",
    "assistant": json.dumps({
        "question": "传统循环神经网络存在长距离依赖问题且无法高效并行化训练。",
        "method": "提出 Transformer 架构，完全基于自注意力机制，去除循环和卷积结构。",
        "metrics": "在 WMT14 英德翻译任务上达到 41.0 BLEU，超越此前最佳模型 2 个点以上。",
        "innovation": "首次完全依赖注意力机制替代循环结构，实现训练阶段的完全并行化。",
        "limitation": "自注意力机制的计算复杂度与序列长度呈二次关系，处理长序列时计算开销较大。"
    }, ensure_ascii=False)
}

REQUIRED_KEYS = ["question", "method", "metrics", "innovation", "limitation"]


def _build_user_prompt(text: str) -> str:
    """构建用户消息"""
    return USER_PROMPT_TEMPLATE.format(text=text[:8000])  # 截断避免超长


def _call_api(messages: list[dict]) -> str:
    """调用 DeepSeek API，带指数退避重试"""
    url = f"{BASE_URL.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 1500,
    }

    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except requests.ConnectionError:
            last_error = Exception("API 连接失败，请检查网络或 BASE_URL")
        except requests.Timeout:
            last_error = Exception("请求超时，请稍后重试")
        except requests.HTTPError as e:
            last_error = Exception(f"API 请求失败：{e.response.status_code}")
        except (KeyError, IndexError):
            last_error = Exception("API 返回格式异常")

        if attempt < MAX_RETRIES - 1:
            wait = BACKOFF_BASE * (2 ** attempt)  # 1s -> 2s -> 4s
            time.sleep(wait)

    raise last_error  # type: ignore[misc]


def _parse_response(raw: str) -> dict:
    """解析 LLM 返回的 JSON，校验字段完整性"""
    # 尝试提取 JSON 子串（防止 LLM 输出多余文字）
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise Exception("JSON 解析失败：返回内容中未找到 JSON 对象")

    try:
        data = json.loads(raw[start:end])
    except json.JSONDecodeError:
        raise Exception("JSON 解析失败：返回内容不是有效 JSON")

    # 填充缺失字段
    for key in REQUIRED_KEYS:
        data.setdefault(key, "")

    # 强制转为字符串并去除首尾空白
    for key in REQUIRED_KEYS:
        data[key] = str(data[key]).strip()

    # === Safeguard: 前四项任一为空 → limitation 强制清空 ===
    core_keys = ["question", "method", "metrics", "innovation"]
    core_missing = [k for k in core_keys if not data[k]]
    if core_missing:
        data["limitation"] = ""
    else:
        # 前四项完整 → 检查 limitation 质量
        limitation = data["limitation"]
        if not limitation or len(limitation) < 15:
            data["limitation"] = (
                "论文未明确讨论局限性，潜在问题可能包括："
                "泛化能力有限、计算开销较大、缺乏真实场景部署验证。"
            )

    return {k: data[k] for k in REQUIRED_KEYS}


def extract_paper_info(text: str) -> dict:
    """
    从论文全文中提取结构化信息

    Args:
        text: 论文全文文本

    Returns:
        包含 question, method, metrics, innovation, limitation 的字典

    Raises:
        Exception: API 调用失败、超时、JSON 解析失败等
    """
    if not API_KEY:
        raise Exception("未配置 DEEPSEEK_API_KEY 环境变量")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": FEWSHOT_EXAMPLE["user"]},
        {"role": "assistant", "content": FEWSHOT_EXAMPLE["assistant"]},
        {"role": "user", "content": _build_user_prompt(text)},
    ]

    raw_response = _call_api(messages)
    return _parse_response(raw_response)


# === 测试入口 ===
if __name__ == "__main__":
    sample_path = os.path.join(os.path.dirname(__file__), "..", "..", "sample.txt")

    if not os.path.exists(sample_path):
        print(f"[错误] 找不到测试文件：{sample_path}")
        print("请在项目根目录创建 sample.txt，放入论文文本后重试")
    else:
        with open(sample_path, "r", encoding="utf-8") as f:
            sample_text = f.read()

        print(f"[信息] 读取样本文件：{len(sample_text)} 字符")
        print("[信息] 调用 LLM API 提取信息...")

        try:
            result = extract_paper_info(sample_text)
            print("[成功] 提取结果：")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"[失败] {e}")
