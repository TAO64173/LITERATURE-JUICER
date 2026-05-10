"""Excel 写入模块

将论文提取结果写入结构化 Excel 文件。
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

# 表头定义
HEADERS = ["论文标题", "研究问题", "研究方法", "性能指标", "创新点", "局限性"]
HEADER_KEYS = ["title", "question", "method", "metrics", "innovation", "limitation"]

# 样式
HEADER_FONT = Font(bold=True, size=11, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
CELL_ALIGN = Alignment(vertical="top", wrap_text=True)
THIN_BORDER = Border(
    left=Side(style="thin", color="D1D5DB"),
    right=Side(style="thin", color="D1D5DB"),
    top=Side(style="thin", color="D1D5DB"),
    bottom=Side(style="thin", color="D1D5DB"),
)
COL_WIDTHS = [30, 35, 35, 25, 30, 30]


def write_excel(papers: list[dict], output_path: str) -> str:
    """
    将论文数据写入 Excel 文件

    Args:
        papers: 论文数据列表，每项包含 title, question, method, metrics, innovation, limitation
        output_path: 输出文件路径

    Returns:
        输出文件的绝对路径
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "文献矩阵"

    # 写表头
    for col, header in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGN
        cell.border = THIN_BORDER

    # 设置列宽
    for col, width in enumerate(COL_WIDTHS, 1):
        ws.column_dimensions[chr(64 + col)].width = width

    # 写数据
    for row_idx, paper in enumerate(papers, 2):
        for col_idx, key in enumerate(HEADER_KEYS, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=paper.get(key, ""))
            cell.alignment = CELL_ALIGN
            cell.border = THIN_BORDER

    # 冻结首行
    ws.freeze_panes = "A2"

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out))
    return str(out.resolve())
