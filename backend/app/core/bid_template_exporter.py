"""模板式商务标导出：以 data/商务标模板.docx 为底稿，替换其中
「三、人员配备表」与「四、相关业绩一览表」两节的表格内容，其余部分原样保留。

表定位策略：按 body 顺序遍历段落/表格，用 Heading 1/2/3 文本（strip 后前缀匹配）
维护当前所在章节状态机：
- H1 "三、人员配备表" 内：首个表格→表A（人员安排）；
  H2 "2、项目负责人" 后的 H3 "（2）项目负责人业绩" 内第 1/2 张表→表B/表C（负责人业绩）；
  H2 "3、项目组人员" 后的表→表D。
- H1 "四、相关业绩一览表" 内：H2 前的首表→表E；H2 "1、…" 后的表→表F；H2 "2、…" 后的表→表G。

行替换：保留表头行，deepcopy 首数据行作为样式 donor 逐条填充后插入，
删除全部原数据行（无记录时即只剩表头）。
"""
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

_HEADING_STYLES = {"Heading 1": 1, "Heading 2": 2, "Heading 3": 3,
                   "标题 1": 1, "标题 2": 2, "标题 3": 3}


def _iter_block_items(doc):
    """按 body 顺序产出 Paragraph / Table。"""
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def _heading_level(para: Paragraph) -> int:
    style = para.style
    return _HEADING_STYLES.get(style.name if style is not None else "", 0)


def _locate_tables(doc) -> dict:
    """定位七张目标表，返回 {role: Table}，role ∈ a/b/c/d/e/f/g。"""
    roles: dict = {}
    section = 0          # 3=人员配备表 / 4=相关业绩一览表 / 0=其他
    sub3 = ""            # 三、内小节：""（表A区）/ lead / lead_perf / members
    sub4 = 0             # 四、内小节：0（表E区）/ 1 / 2
    lead_perf_tables = 0
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            level = _heading_level(block)
            if not level:
                continue
            text = block.text.strip()
            if level == 1:
                if text.startswith("三、人员配备表"):
                    section, sub3, sub4 = 3, "", 0
                elif text.startswith("四、相关业绩一览表"):
                    section, sub3, sub4 = 4, "", 0
                else:
                    section = 0
            elif section == 3 and level == 2:
                if text.startswith("2、"):
                    sub3 = "lead"
                elif text.startswith("3、项目组人员"):
                    sub3 = "members"
            elif section == 3 and level == 3 and text.startswith("（2）项目负责人业绩"):
                sub3 = "lead_perf"
                lead_perf_tables = 0
            elif section == 4 and level == 2:
                if text.startswith("1、"):
                    sub4 = 1
                elif text.startswith("2、"):
                    sub4 = 2
        else:  # Table
            if section == 3:
                if sub3 == "":
                    roles.setdefault("a", block)
                elif sub3 == "lead_perf":
                    lead_perf_tables += 1
                    roles.setdefault("b" if lead_perf_tables == 1 else "c", block)
                elif sub3 == "members":
                    roles.setdefault("d", block)
            elif section == 4:
                if sub4 == 0:
                    roles.setdefault("e", block)
                elif sub4 == 1:
                    roles.setdefault("f", block)
                elif sub4 == 2:
                    roles.setdefault("g", block)
    return roles


def _set_cell_text(cell, text: str) -> None:
    """写单元格文本（\n 转软换行），尽量保留首段/首 run 的格式。"""
    lines = str(text if text is not None else "").split("\n")
    para = cell.paragraphs[0]
    for p in cell.paragraphs[1:]:
        p._element.getparent().remove(p._element)
    if para.runs:
        run = para.runs[0]
        for r in para.runs[1:]:
            r._element.getparent().remove(r._element)
    else:
        run = para.add_run()
    run.text = lines[0]
    for line in lines[1:]:
        run.add_break()
        run.add_text(line)


def _fill_table(table: Table, rows_data: list) -> None:
    """数据行整体替换：保留表头；无数据时仅留表头。"""
    rows = table.rows
    donor_tr = deepcopy(rows[1]._tr if len(rows) >= 2 else rows[0]._tr)
    for r in list(table.rows[1:]):
        r._tr.getparent().remove(r._tr)
    for data in rows_data or []:
        table._tbl.append(deepcopy(donor_tr))
        new_row = table.rows[-1]
        for idx, cell in enumerate(new_row.cells):
            _set_cell_text(cell, data[idx] if idx < len(data) else "")


def build_bid_docx_from_template(template_path: str, dest_path: str, data: dict) -> Path:
    """以模板为底稿填充七张表。data: {"a".."g": 各行列表}（assemble_bid_template_data 产出）。"""
    doc = Document(template_path)
    tables = _locate_tables(doc)
    for role, rows in (data or {}).items():
        table = tables.get(role)
        if table is not None:
            _fill_table(table, rows or [])
    dest = Path(dest_path)
    doc.save(str(dest))
    return dest
