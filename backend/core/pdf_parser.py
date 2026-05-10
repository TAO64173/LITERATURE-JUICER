"""PDF 文本提取模块

使用 PyMuPDF 提取论文核心内容，跳过参考文献，清洗噪音。
"""

import re
import fitz  # PyMuPDF


# 参考文献页识别关键词
_REF_KEYWORDS = re.compile(
    r"^\s*(references|bibliography|参考文献|引用文献)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# 短文本噪音阈值（字符数）
_MIN_LINE_LEN = 5


def _is_reference_page(text: str) -> bool:
    """判断页面是否为参考文献页"""
    return bool(_REF_KEYWORDS.search(text))


def _clean_text(text: str) -> str:
    """清洗文本：去空行、去短噪音行"""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) < _MIN_LINE_LEN:
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned)


def extract_text(pdf_path: str) -> str:
    """
    从 PDF 提取核心文本内容

    策略：
    1. 提取前 3 页
    2. 提取倒数 3 页
    3. 跳过识别到的参考文献页
    4. 清洗后返回纯文本

    Args:
        pdf_path: PDF 文件路径

    Returns:
        清洗后的纯文本内容

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 无法打开 PDF
    """
    doc = fitz.open(pdf_path)

    if doc.page_count == 0:
        doc.close()
        raise ValueError("PDF 文件为空，无法提取内容")

    total = doc.page_count

    # 确定要提取的页面范围
    front_pages = list(range(min(3, total)))
    back_pages = list(range(max(0, total - 3), total))
    page_indices = list(dict.fromkeys(front_pages + back_pages))  # 去重保序

    raw_parts: list[str] = []

    for idx in page_indices:
        page_text = doc[idx].get_text()

        # 跳过参考文献页
        if _is_reference_page(page_text):
            continue

        raw_parts.append(page_text)

    doc.close()

    # 合并并清洗
    full_text = "\n".join(raw_parts)
    return _clean_text(full_text)
