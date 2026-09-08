"""商务标底稿裁切：从招标文件 docx 中定位「投标文件格式」章节，
按 body 子元素区间 [start, end) 原样保留（XML 不动，样式/页眉页脚/sectPr 全继承），
区间外元素删除。产出底稿 docx + 预览大纲 + 顶层表格数。

已知限制：若格式章节前有分节符挂在被删段落上，页面设置会退化为文档末
sectPr；实测样本均为单一节，不处理。
"""
import re
import shutil

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from app.core.bid_template_exporter import _is_toc_paragraph
from app.core.template_outline import _strip_tab_pageno, para_heading_level


class BidDraftError(Exception):
    """底稿裁切失败（路由据此返回 400/422）。"""


FORMAT_CHAPTER_KEYWORDS = (
    "投标文件格式", "响应文件格式", "磋商响应文件格式",
    "谈判响应文件格式", "报价文件格式", "资格证明文件格式",
)

_WS_RE = re.compile(r"\s+")

_FAMILY_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百零]+[章篇部]")
_FAMILY_NUMBERED_RE = re.compile(r"^\d+(?:\.\d+)*[、．.\s]")


def _title_family(title: str) -> str:
    """标题族判定：numbered = 数字编号条目（"1.投标函；""1、适用范围"等）。
    此类条目多为章内列表项（真实招标文件里被文本兜底判为 H1），
    不应作为格式章节的结束边界。"""
    t = (title or "").strip()
    if _FAMILY_CHAPTER_RE.match(t):
        return "chapter"
    if _FAMILY_NUMBERED_RE.match(t):
        return "numbered"
    return "other"


def list_headings(docx_path: str) -> list:
    """扫描 body 顶层子元素，返回标题列表 [{"index", "level", "title"}]。

    index 为该段在 body 子元素中的下标（含正文段/表格占位），
    供 API 边界选择与 cut_draft 裁切共用同一坐标系；
    正文段/表格不收录但占下标。标题判定复用 para_heading_level
    （样式优先 + 文本模式兜底），标题尾部 制表符+页码 防御性剥离。
    """
    doc = Document(docx_path)
    headings = []
    for index, child in enumerate(doc.element.body.iterchildren()):
        if child.tag != qn("w:p"):
            continue
        para = Paragraph(child, doc)
        level = para_heading_level(para)
        if level > 0:
            title = _strip_tab_pageno(para.text)
            if title:
                headings.append({"index": index, "level": level, "title": title})
    return headings


def find_format_chapter(headings: list):
    """在 list_headings 结果中定位「投标文件格式」章节。

    仅匹配 level ≤ 2 的标题；命中 = 标题（去全部空白后）含
    FORMAT_CHAPTER_KEYWORDS 任一关键词；多个命中取最后一个。
    返回 {"start": {...}, "end": {...} | None}；end = 其后的、
    level <= start.level 的第一个标题（无 → None，表示到文档末尾）；
    数字编号条目（"1.××"）不作 end 边界（除非起始标题本身也是数字编号族）。
    无命中 → None。
    """
    start = None
    for h in headings:
        if h["level"] > 2:
            continue
        compact = _WS_RE.sub("", h["title"])
        if any(kw in compact for kw in FORMAT_CHAPTER_KEYWORDS):
            start = h  # 持续覆盖 → 取最后一个命中
    if start is None:
        return None
    end = None
    seen_start = False
    start_fam = _title_family(start["title"])
    for h in headings:
        if h is start:
            seen_start = True
            continue
        if not seen_start or h["level"] > start["level"]:
            continue
        if start_fam != "numbered" and _title_family(h["title"]) == "numbered":
            continue  # 章内数字编号条目不是结构边界
        end = h
        break
    return {"start": start, "end": end}


def cut_draft(tender_docx: str, dest_path: str,
              start_index: int, end_index: int = -1) -> dict:
    """从招标文件裁出 [start_index, end_index) 区间为商务标底稿。

    先整文件复制再删区间外 body 子元素（始终保留 w:sectPr，删除手法参照
    word_exporter._clear_body_keep_cover），区间内 XML 原样保留。
    end_index <= 0 表示裁切到文档末尾。
    start_index 越界或（end_index > 0 且 start_index >= end_index）
    → BidDraftError("裁切区间为空，请调整起止标题")。

    返回 {"outline": [(level, title), ...]（裁切区间内标题序列）,
          "tables": int（裁切区间内顶层表格数）,
          "toc_paragraphs": int（裁切后文档中 toc 样式段落数）}。
    """
    shutil.copy(tender_docx, dest_path)
    doc = Document(dest_path)
    body = doc.element.body
    children = list(body)
    if start_index < 0 or start_index >= len(children) \
            or (end_index > 0 and start_index >= end_index):
        raise BidDraftError("裁切区间为空，请调整起止标题")
    end = end_index if end_index > 0 else len(children)

    # 裁切区间内统计（删除前基于原坐标系计算）
    outline = []
    tables = 0
    for child in children[start_index:end]:
        if child.tag == qn("w:p"):
            para = Paragraph(child, doc)
            level = para_heading_level(para)
            if level > 0:
                title = _strip_tab_pageno(para.text)
                if title:
                    outline.append((level, title))
        elif child.tag == qn("w:tbl"):
            tables += 1

    # 删除区间外元素（始终保留 sectPr）
    for el in children[:start_index] + children[end:]:
        if el.tag == qn("w:sectPr"):
            continue
        body.remove(el)
    doc.save(dest_path)

    toc_paragraphs = sum(1 for para in Document(dest_path).paragraphs
                         if _is_toc_paragraph(para))
    return {"outline": outline, "tables": tables,
            "toc_paragraphs": toc_paragraphs}


def resolve_heading_index(headings: list, title: str) -> int:
    """按标题文本（strip）在 list_headings 结果中取首个命中的 body 下标；
    无命中 → BidDraftError。"""
    target = title.strip()
    for h in headings:
        if h["title"].strip() == target:
            return h["index"]
    raise BidDraftError(f"未找到标题：{title}")
