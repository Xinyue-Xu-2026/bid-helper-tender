"""底稿填充防篡改校验：产物 vs 底稿逐块对比——
未绑定表格（含嵌套）所有单元格文本必须逐一相等；
正文段落文本在套用与导出相同的编号/名称/日期替换规则后必须相等。
命中差异即不得修改内容被改动。"""
from docx import Document
from docx.text.paragraph import Paragraph

from app.core.bid_template_exporter import (
    _is_toc_paragraph, _iter_block_items, _iter_cell_paragraphs, _para_text,
    compute_text_subs,
)


def _table_texts(table) -> list:
    """递归收集表格全部单元格内段落文本（含嵌套表），按行/列/段顺序。"""
    texts = []
    for row in table.rows:
        for cell in row.cells:
            for para in _iter_cell_paragraphs(cell):
                texts.append(_para_text(para))
    return texts


def _apply_subs(text: str, subs) -> str:
    """对底稿段文本套用替换规则得期望文本。"""
    for pattern, repl in subs:
        text = pattern.sub(repl, text)
    return text


def verify_draft_fill(draft_path: str, out_path: str,
                      bound_table_indices: set, replace_params: dict,
                      swapped_toc: bool = False) -> dict:
    """校验产物相对底稿的未绑定区域是否被改动。

    bound_table_indices：已确认绑定（允许填充改动）的顶层表下标集合，
    这些表整体跳过比对（其内部段落本就不参与正文段比对）。
    replace_params：{"project_no","project_name","doc_date"}，与导出时一致；
    空/某键空 → compute_text_subs 相应无规则，套用无害。
    swapped_toc=True 时两侧 toc 样式段落均跳过（导出已将其整段换为 TOC 域）。
    返回 {"ok": bool, "issues": [str], "checked_paragraphs": int,
    "checked_tables": int}。
    """
    draft = Document(draft_path)
    out = Document(out_path)
    params = replace_params or {}
    subs = compute_text_subs(
        draft,
        project_no=str(params.get("project_no") or ""),
        project_name=str(params.get("project_name") or ""),
        doc_date=str(params.get("doc_date") or ""))

    def _split(doc):
        paras, tables = [], []
        for block in _iter_block_items(doc):
            if isinstance(block, Paragraph):
                paras.append(block)
            else:
                tables.append(block)
        return paras, tables

    d_paras, d_tables = _split(draft)
    o_paras, o_tables = _split(out)

    issues = []
    checked_paragraphs = 0
    checked_tables = 0
    bound = set(bound_table_indices or set())

    # 顶层表数量：bound 之外的未绑定表数必须一致（总数一致即等价）
    if len(d_tables) != len(o_tables):
        issues.append(
            f"顶层表格数量不一致：底稿 {len(d_tables)} 张，产物 {len(o_tables)} 张")
    for i, (d_tab, o_tab) in enumerate(zip(d_tables, o_tables)):
        if i in bound:
            continue
        checked_tables += 1
        if _table_texts(d_tab) != _table_texts(o_tab):
            issues.append(f"表格[{i}] 未绑定但内容被改动")

    # 段落：swapped_toc 时两侧 toc 段均跳过
    if swapped_toc:
        d_paras = [p for p in d_paras if not _is_toc_paragraph(p)]
        o_paras = [p for p in o_paras if not _is_toc_paragraph(p)]
    if len(d_paras) != len(o_paras):
        issues.append(
            f"段落数量不一致：底稿 {len(d_paras)} 段，产物 {len(o_paras)} 段")
    for i, (d_para, o_para) in enumerate(zip(d_paras, o_paras)):
        checked_paragraphs += 1
        expected = _apply_subs(_para_text(d_para), subs)
        if expected != _para_text(o_para):
            snippet = _para_text(d_para)[:30]
            issues.append(f'段落[{i}] "{snippet}" 内容被改动')

    return {"ok": not issues, "issues": issues,
            "checked_paragraphs": checked_paragraphs,
            "checked_tables": checked_tables}
