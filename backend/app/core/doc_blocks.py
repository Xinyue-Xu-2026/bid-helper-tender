"""底稿块序列读写（结构保真内容编辑器，方案 A）。

read_blocks：把底稿 docx 的 body 按序读成「块序列」——段落块（文本）与
表格块（逻辑网格：vMerge/gridSpan 展开为 {text, colspan, rowspan, origin}）。

apply_edits：把编辑（段落文本 / 表格格子文本 / 复制表）**原位**应用到一份
副本，绝不重建文档——合并单元格、行列数、行高、字体样式逐字节保留；
复制表复用 _clone_table_after（XML 级 deepcopy + 表间空段分隔）。

编辑只改「文字内容」，不改任何结构/格式（复制表是唯一的显式结构操作）。
"""
from copy import deepcopy

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table, _Cell

from app.core.bid_draft_exporter import _clone_table_after, expand_table_matrix
from app.core.bid_template_exporter import (
    _el_has_nontext, _iter_block_items, _para_text, _set_cell_text,
)


def _iter_grid_cells(table):
    """按逻辑网格行优先产出每个「首格」：{r, c, tc, colspan, rowspan, origin}。
    与 expand_table_matrix 同坐标系；colspan=gridSpan、rowspan=vMerge 纵向
    延展行数、origin=该格是否为该 origin tc 的左上角（续行/续列格 origin=False）。
    """
    matrix = expand_table_matrix(table)
    nrows = len(matrix)
    for r, row in enumerate(matrix):
        ncols = len(row)
        c = 0
        while c < ncols:
            tc = row[c]
            cs = 1
            while c + cs < ncols and row[c + cs] is tc:
                cs += 1
            rs = 1
            while (r + rs < nrows and len(matrix[r + rs]) > c
                   and matrix[r + rs][c] is tc):
                rs += 1
            origin = ((r == 0 or matrix[r - 1][c] is not tc)
                      and (c == 0 or row[c - 1] is not tc))
            yield {"r": r, "c": c, "tc": tc, "colspan": cs,
                   "rowspan": rs, "origin": origin}
            c += cs


def _table_rows(table):
    """把 _iter_grid_cells 按行分组，返回 [[cell_dict, ...], ...]。"""
    rows = []
    cur = []
    cur_r = None
    for g in _iter_grid_cells(table):
        if cur_r is not None and g["r"] != cur_r:
            rows.append(cur)
            cur = []
        cur_r = g["r"]
        cur.append(g)
    if cur:
        rows.append(cur)
    return rows


def _cell_text(table, tc) -> str:
    return _Cell(tc, table).text or ""


def read_blocks(docx_path: str) -> dict:
    """读底稿为块序列。返回 {"blocks": [...], "n_tables": int}。"""
    doc = Document(docx_path)
    blocks = []
    p_idx = 0
    t_idx = 0
    for block in _iter_block_items(doc):
        if isinstance(block, Table):
            rows = []
            for group in _table_rows(block):
                rows.append([{
                    "text": _cell_text(block, g["tc"]) if g["origin"] else "",
                    "colspan": g["colspan"],
                    "rowspan": g["rowspan"],
                    "origin": g["origin"],
                } for g in group])
            blocks.append({"kind": "table", "index": t_idx, "rows": rows,
                           "ncols": len(block.columns)})
            t_idx += 1
        else:  # Paragraph
            blocks.append({"kind": "paragraph", "index": p_idx,
                           "text": _para_text(block)})
            p_idx += 1
    return {"blocks": blocks, "n_tables": t_idx}


def _write_para_text(para, text: str) -> None:
    """原位写段落文本（\n → 软换行），保留含 drawing/pict 的 run（首 run 取
    首个文本 run，若首 run 即非文本 run 则在其后新增文本 run 前先取文本 run）。"""
    lines = str(text if text is not None else "").split("\n")
    text_runs = [r for r in para.runs if not _el_has_nontext(r._element)]
    if text_runs:
        run = text_runs[0]
        for r in text_runs[1:]:
            r._element.getparent().remove(r._element)
    else:
        run = para.add_run()
    run.text = lines[0]
    for line in lines[1:]:
        run.add_break()
        run.add_text(line)


def apply_edits(docx_path: str, out_path: str, paragraphs: dict = None,
                tables: dict = None, clones: list = None) -> dict:
    """把编辑应用到底稿副本 out_path（不得与 docx_path 同路径）。

    paragraphs: {段落序: 文本}；tables: {表序: [[文本,...] 按行与 read_blocks
    rows 对齐]}；clones: [{"table_index": idx, "count": n}]（复制 n 份）。
    返回 {"paragraphs": 改段落数, "cells": 改格数, "cloned": 复制表数}。
    """
    import os
    if os.path.abspath(str(docx_path)) == os.path.abspath(str(out_path)):
        raise ValueError("out_path 不得与 docx_path 同路径")
    doc = Document(docx_path)
    paragraphs = {int(k): v for k, v in (paragraphs or {}).items()}
    table_edits = {int(k): v for k, v in (tables or {}).items()}

    # 1) 结构操作（复制表）先做：文本编辑的表下标是「克隆后」的下标（前端读的
    # 是克隆后状态），故复制必须先于文本编辑，坐标系才一致。
    cloned = 0
    for spec in (clones or []):
        idx = int(spec.get("table_index"))
        n = int(spec.get("count") or 0)
        if not (0 <= idx < len(doc.tables)):
            continue
        anchor = doc.tables[idx]
        for _ in range(n):
            anchor = _clone_table_after(anchor)
            cloned += 1

    # 2) 文本编辑（段落 / 表格格子，原位写）
    p_idx = 0
    t_idx = 0
    cells_written = 0
    paras_written = 0
    for block in _iter_block_items(doc):
        if isinstance(block, Table):
            edits = table_edits.get(t_idx)
            if edits:
                flat = []
                for row in edits:
                    flat.extend(row)
                groups = [g for group in _table_rows(block) for g in group]
                for i, g in enumerate(groups):
                    if not g["origin"]:
                        continue
                    if i < len(flat):
                        _set_cell_text(_Cell(g["tc"], block), str(flat[i] or ""))
                        cells_written += 1
            t_idx += 1
        else:
            if p_idx in paragraphs:
                _write_para_text(block, paragraphs[p_idx])
                paras_written += 1
            p_idx += 1

    doc.save(str(out_path))
    return {"paragraphs": paras_written, "cells": cells_written,
            "cloned": cloned}
