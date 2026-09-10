"""底稿填充防篡改校验：产物 vs 底稿逐块对比——
未绑定表格（含嵌套）所有单元格文本在套用与导出相同的编号/名称/日期
替换规则后必须逐一相等；正文段落文本同样套规则后比对。
命中差异即不得修改内容被改动。"""
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from app.core.bid_template_exporter import (
    _is_toc_paragraph, _iter_block_items, _iter_cell_paragraphs,
    _iter_textbox_paragraphs, _para_text, compute_text_subs,
)


def _is_section_break_para(para) -> bool:
    """分节符段落（pPr 内含 sectPr，无正文内容）——页面设置（P2）拆节
    会在产物中插入此类段落，属格式变化而非内容改动，比对时跳过。"""
    pPr = para._p.find(qn("w:pPr"))
    return pPr is not None and pPr.find(qn("w:sectPr")) is not None


def _apply_subs(text: str, subs) -> str:
    """对底稿段文本套用替换规则得期望文本。"""
    for pattern, repl in subs:
        text = pattern.sub(repl, text)
    return text


def _table_texts(table, subs=None) -> list:
    """递归收集表格全部单元格内段落文本（含嵌套表），按行/列/段顺序。
    subs 非空时逐段套用替换规则（toc 样式段除外——导出的
    _replace_stale_text 对表格内段落同样跳过 toc 段，保持对称）。"""
    texts = []
    for row in table.rows:
        for cell in row.cells:
            for para in _iter_cell_paragraphs(cell):
                text = _para_text(para)
                if subs and not _is_toc_paragraph(para):
                    text = _apply_subs(text, subs)
                texts.append(text)
    return texts


def _textbox_texts(doc, subs=None) -> list:
    """收集**表外**文本框（含嵌套）内段落文本；subs 非空时逐段套用替换
    规则（toc 样式段除外，与导出侧 _replace_stale_text 对称）。

    仅比对表外文本框：文本框位于表格单元格内时属表格/克隆表内容——绑定表
    本就不参与文本比对，且 resume_each 整表克隆会复制表内文本框，若按
    全文逐段比对会因数量/内容不对称而误报（违反"防篡改不误报"）。封面
    占位文本框（V1.2 4.2）均为表外段落，不受此收窄影响。"""
    out = []
    for p in _iter_textbox_paragraphs(doc):
        if any(a.tag == qn("w:tbl") for a in p._p.iterancestors()):
            continue
        t = _para_text(p)
        if subs and not _is_toc_paragraph(p):
            t = _apply_subs(t, subs)
        out.append(t)
    return out


def verify_draft_fill(draft_path: str, out_path: str,
                      bound_table_indices: set, replace_params: dict,
                      swapped_toc: bool = False,
                      bound_paragraph_indices: set = None,
                      table_insertions: dict = None) -> dict:
    """校验产物相对底稿的未绑定区域是否被改动。

    bound_table_indices：已确认绑定（允许填充改动）的顶层表下标集合，
    这些表整体跳过比对（其内部段落本就不参与正文段比对）。
    bound_paragraph_indices：授权页等经用户确认允许正文填充改动的段落
    下标集合（toc/分节符/空段过滤后的段落序列坐标系，与比对循环一致），
    这些段落整体跳过比对。默认空集。
    table_insertions：{底稿表下标: 其后插入的克隆表数}（resume_each
    一人一表整表克隆，V1.2 7.4）；克隆表无底稿对应，计入产物表数量
    等式且不参与比对，底稿表按下标位移映射到产物表。默认空。
    replace_params：{"project_no","project_name","doc_date","tenderer",
    "bidder_name","section_name","section_no","synonyms"}，与导出时一致；
    空/某键空 → compute_text_subs 相应无规则，套用无害。
    toc 样式段落两侧恒跳过（导出的 _replace_stale_text 从不触碰 toc 段）；
    swapped_toc=True 时产物 toc 段已整组换为 TOC 域，同样由该跳过覆盖。
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
        doc_date=str(params.get("doc_date") or ""),
        tenderer=str(params.get("tenderer") or ""),
        bidder_name=str(params.get("bidder_name") or ""),
        section_name=str(params.get("section_name") or ""),
        section_no=str(params.get("section_no") or ""),
        synonyms=params.get("synonyms"))

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
    bound_paras = set(bound_paragraph_indices or set())

    # 顶层表数量：bound 之外的未绑定表数必须一致；resume_each 克隆表
    # （table_insertions）无底稿对应，计入产物数量等式且不参与比对
    insertions = {int(k): int(v) for k, v in (table_insertions or {}).items()}
    total_added = sum(insertions.values())
    if len(o_tables) != len(d_tables) + total_added:
        issues.append(
            f"顶层表格数量不一致：底稿 {len(d_tables)} 张，"
            f"产物 {len(o_tables)} 张（含登记克隆 {total_added} 张）")
    # 底稿表下标 → 产物表下标（克隆插入使其后表整体位移）
    draft_to_out, shift = {}, 0
    for i in range(len(d_tables)):
        draft_to_out[i] = i + shift
        shift += insertions.get(i, 0)
    for i, d_tab in enumerate(d_tables):
        if i in bound:
            continue
        oi = draft_to_out[i]
        if oi >= len(o_tables):
            continue  # 数量不一致已报，跳过防越界
        o_tab = o_tables[oi]
        checked_tables += 1
        # 底稿侧套用与导出相同的替换规则（_replace_stale_text 会改写
        # 未绑定表单元格内的残留编号/名称/日期），产物侧原样比对
        if _table_texts(d_tab, subs) != _table_texts(o_tab):
            issues.append(f"表格[{i}] 未绑定但内容被改动")

    # 段落：toc 样式段两侧恒跳过（_replace_stale_text 从不触碰 toc 段；
    # swapped_toc 时产物 toc 段整组换为 TOC 域，同样被跳过覆盖）；
    # 分节符段落（P2 拆节插入）同样跳过；空段（无文本）不携带内容、
    # 两侧恒跳过——克隆表分隔空段（resume_each 一人一表插入）等结构性
    # 变化不视为内容改动；注意仅含图片（无文本）的段落同属空段，
    # 不参与段落比对（图片改动由表格/文本框维度覆盖不到，属已知豁免），
    # bound_paragraph_indices 坐标系同为「非空段」
    d_paras = [p for p in d_paras if not _is_toc_paragraph(p)
               and not _is_section_break_para(p) and _para_text(p)]
    o_paras = [p for p in o_paras if not _is_toc_paragraph(p)
               and not _is_section_break_para(p) and _para_text(p)]
    if len(d_paras) != len(o_paras):
        issues.append(
            f"段落数量不一致：底稿 {len(d_paras)} 段，产物 {len(o_paras)} 段")
    for i, (d_para, o_para) in enumerate(zip(d_paras, o_paras)):
        if i in bound_paras:
            continue
        checked_paragraphs += 1
        expected = _apply_subs(_para_text(d_para), subs)
        if expected != _para_text(o_para):
            snippet = _para_text(d_para)[:30]
            issues.append(f'段落[{i}] "{snippet}" 内容被改动')

    # 文本框：底稿侧套用同一套替换规则后与产物逐段比对
    d_txbx = _textbox_texts(draft, subs)
    o_txbx = _textbox_texts(out)
    if d_txbx != o_txbx:
        if len(d_txbx) != len(o_txbx):
            issues.append(
                f"文本框内容被改动：底稿 {len(d_txbx)} 段，产物 {len(o_txbx)} 段")
        else:
            for i, (d_t, o_t) in enumerate(zip(d_txbx, o_txbx)):
                if d_t != o_t:
                    issues.append(f"文本框段落[{i}] 内容被改动")

    return {"ok": not issues, "issues": issues,
            "checked_paragraphs": checked_paragraphs,
            "checked_tables": checked_tables}
