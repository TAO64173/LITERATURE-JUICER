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
TIMEOUT = 90
BACKOFF_BASE = 1  # 秒


# === 字段定义 ===
# LLM 提取的字段（title 由文件名生成，不在此列）
LLM_KEYS = [
    "author", "year", "journal", "doi", "keywords", "abstract",
    "question", "background", "gap", "objective",
    "method", "dataset", "metrics", "comparison",
    "innovation", "findings", "conclusion",
    "limitation", "future_work", "inspiration",
]

# 元数据字段（英文原文保留）
METADATA_KEYS = {"author", "year", "journal", "doi", "keywords", "abstract"}

# 分析类字段（中文输出）
ANALYSIS_KEYS = {
    "question", "background", "gap", "objective",
    "method", "dataset", "metrics", "comparison",
    "innovation", "findings", "conclusion",
    "limitation", "future_work", "inspiration",
}

# 用于 limitation 质量检查的核心字段
CORE_KEYS = ["question", "method", "innovation"]

REQUIRED_KEYS = LLM_KEYS


# === Prompt 构建 ===
SYSTEM_PROMPT = """你是一个顶级科研助手，擅长深度阅读机器学习、人工智能、机器人、自动驾驶、NLP、CV 等领域论文。

你的任务不是简单摘抄，而是像资深 researcher 一样精读论文并提取核心信息。

【输出格式】
严格输出 JSON object，字段如下：

{
  "author": "",
  "year": "",
  "journal": "",
  "doi": "",
  "keywords": "",
  "abstract": "",
  "question": "",
  "background": "",
  "gap": "",
  "objective": "",
  "method": "",
  "dataset": "",
  "metrics": "",
  "comparison": "",
  "innovation": "",
  "findings": "",
  "conclusion": "",
  "limitation": "",
  "future_work": "",
  "inspiration": ""
}

【字段详细要求】

一、元数据字段（保留英文原文）：

author（作者）：
- 提取第一作者 + et al.，如 "Vaswani et al."
- 若为单作者，直接写姓名

year（发表年份）：
- 仅输出数字，如 "2023"

journal（期刊/会议）：
- 提取期刊或会议名称，如 "NeurIPS"、"CVPR"、"Nature"
- 未标注则写 "未明确标注"

doi（DOI）：
- 提取论文的 DOI 标识符
- 若无 DOI，输出 "未明确标注"

keywords（关键词）：
- 提取论文的关键词，用英文逗号分隔
- 如 "attention mechanism, transformer, self-supervised learning"
- 若论文无明确关键词，从 abstract 中提炼 3-5 个核心术语

abstract（摘要）：
- 提取论文的 abstract 摘要内容
- 保留英文原文
- 若无明确 abstract，用 1-2 句话概括论文核心内容

二、分析类字段（全部用中文）：

question（研究问题）：
- 论文要解决什么具体问题
- 1-2 句话

background（研究背景）：
- 研究领域的背景信息
- 该领域的发展现状
- 1-2 句话

gap（研究动机/研究空白）：
- 现有工作存在什么不足或空白
- 作者为什么要做这项研究
- 1-2 句话

objective（研究目标）：
- 作者希望通过这项研究达到什么目标
- 1-2 句话

method（研究方法）：
- 核心方法、模型架构、技术路线
- 1-2 句话

dataset（数据集/实验设置）：
- 使用的数据集名称和规模
- 实验环境和设置
- 1-2 句话

metrics（性能指标）：
- 最重要的实验结果，包含关键数值
- 如 "在 ImageNet 上达到 88.5% Top-1 准确率，超越 SOTA 2.3 个百分点"
- 保留数值和指标名称

comparison（对比方法）：
- 与哪些 baseline 或 SOTA 方法进行了对比
- 1-2 句话

innovation（创新点）：
- 相比已有工作，本文的核心新贡献是什么
- 1-2 句话

findings（关键发现）：
- 实验中发现的重要现象或结论
- 消融实验的关键发现
- 1-2 句话

conclusion（主要结论）：
- 作者在论文中得出的核心结论
- 1-2 句话

limitation（局限性）：
- 优先从论文的 limitation、discussion、future work 章节提取
- 如果论文未明确说明，基于论文内容合理推断
- 长度不少于 15 个字

future_work（未来工作）：
- 作者提出的未来研究方向
- 如果论文未明确说明，基于论文内容合理推断
- 1-2 句话

inspiration（可借鉴点/启发）：
- 这篇论文对其他研究者的启发和可借鉴之处
- 可复用的方法、思路或技术
- 1-2 句话

【阅读顺序】
你必须按以下顺序精读论文：
1. title + abstract + keywords → 提取元数据 + question + objective
2. introduction → 提取 background + gap + motivation
3. method section → 提取 method + innovation
4. experiments/results → 提取 dataset + metrics + comparison + findings
5. conclusion/discussion/limitation → 提取 conclusion + limitation + future_work + inspiration

【输出规则】
1. 仅输出 JSON object
2. 不输出 markdown、不输出 ```json
3. 不输出任何解释文字
4. 元数据字段保留英文原文
5. 分析类字段全部用中文
6. 某字段论文中确实不存在时，输出 "未明确提及"
7. 所有字段不得留空"""

USER_PROMPT_TEMPLATE = """请精读以下论文内容，按照系统指令的阅读顺序，依次提取全部 20 个字段。

论文内容：
{text}

严格只输出 JSON object，不要 markdown，不要解释。"""

FEWSHOT_EXAMPLE = {
    "user": "请提取以下论文信息：Transformer: Attention Is All You Need",
    "assistant": json.dumps({
        "author": "Vaswani et al.",
        "year": "2017",
        "journal": "NeurIPS",
        "doi": "10.48550/arXiv.1706.03762",
        "keywords": "attention mechanism, transformer, self-attention, sequence transduction",
        "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.",
        "question": "传统循环神经网络在处理长序列时存在梯度消失问题，且无法高效并行化训练。",
        "background": "序列到序列模型主要依赖 RNN 及其变体（LSTM、GRU），在机器翻译等任务中广泛应用，但存在训练效率低下的问题。",
        "gap": "现有 RNN 及其变体在长距离依赖建模上表现受限，且序列处理的串行特性严重制约训练效率。",
        "objective": "提出一种完全基于注意力机制的新型序列转导模型，替代循环结构以实现高效并行训练。",
        "method": "提出 Transformer 架构，完全基于多头自注意力机制和前馈网络，去除循环和卷积结构，引入位置编码。",
        "dataset": "WMT14 英德翻译数据集（450万句对），WMT14 英法翻译数据集（3600万句对）。",
        "metrics": "在 WMT14 英德翻译任务上达到 41.0 BLEU，超越此前最佳模型 2 个点以上，训练时间大幅缩短。",
        "comparison": "与基于 LSTM 的编码器-解码器模型、ConvS2S 模型等当时最先进的序列转导模型进行对比。",
        "innovation": "首次完全依赖注意力机制替代循环结构，实现训练阶段的完全并行化，并引入多头注意力机制增强表征能力。",
        "findings": "消融实验表明多头注意力和位置编码对性能至关重要，模型在长距离依赖任务上显著优于 RNN。",
        "conclusion": "Transformer 架构在机器翻译任务上取得了当时的最佳结果，证明了纯注意力模型的有效性。",
        "limitation": "自注意力机制的计算复杂度与序列长度呈二次关系，处理超长序列时计算开销较大；模型对位置编码方式敏感。",
        "future_work": "探索更高效的注意力机制以处理更长序列，将 Transformer 应用于其他任务领域如图像和语音。",
        "inspiration": "纯注意力架构的设计思路可迁移到各类序列建模任务，多头注意力机制为特征融合提供了新范式。"
    }, ensure_ascii=False)
}


def _build_user_prompt(text: str) -> str:
    """构建用户消息"""
    return USER_PROMPT_TEMPLATE.format(text=text[:12000])


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
        "max_tokens": 2500,
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
        data.setdefault(key, "未明确提及")

    # 强制转为字符串并去除首尾空白
    for key in REQUIRED_KEYS:
        data[key] = str(data[key]).strip()

    # 元数据字段：若为空则设为 "未明确提及"
    for key in METADATA_KEYS:
        if not data[key]:
            data[key] = "未明确提及"

    # 分析类字段：若为空则设为 "未明确提及"
    for key in ANALYSIS_KEYS:
        if not data[key]:
            data[key] = "未明确提及"

    # limitation 质量检查：确保长度不少于 15 字
    limitation = data["limitation"]
    if limitation == "未明确提及" or len(limitation) < 15:
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
        包含全部 14 个 LLM 提取字段的字典

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
