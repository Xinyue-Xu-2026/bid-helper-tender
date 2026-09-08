"""模板章节解析与篇幅统计。

- parse_outline：按 python-docx 读段落 style（Heading/标题 1-4）提取章节标题；
  样式不规范时按文本模式兜底（第X章 / X、 / （X） / 数字编号）。
- section_target_chars：统计模板中某章节（本标题到下一同级/更高级标题之间，
  含子节正文）的正文实测字数；找不到时取同级章节平均，无同级时取全体平均，兜底 3000。
"""
import re
from pathlib import Path

DEFAULT_TARGET_CHARS = 3000

_HEADING_STYLE_RE = re.compile(r"^(heading|标题)\s*([1-4])$", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百零]+章")
_SECTION_RE = re.compile(r"^[一二三四五六七八九十]+、")
_SUBSECTION_RE = re.compile(r"^[（(][一二三四五六七八九十]+[)）]")
_NUMBERED_RE = re.compile(r"^(\d+(?:\.\d+)*)[、．.\s]+\S")

# TOC（目录）污染判定：样式名 toc/目录 开头、文本以 制表符+页码 结尾、含 TOC 域代码
_TOC_STYLE_RE = re.compile(r"^(toc|目录)", re.IGNORECASE)
_TAB_PAGENO_RE = re.compile(r"\t\s*[0-9IVXLCDM]+\s*$", re.IGNORECASE)

_WS_RE = re.compile(r"\s+")


def _strip_tab_pageno(title: str) -> str:
    """防御性剥离标题尾部的 制表符+页码（及残留空白）。"""
    return _TAB_PAGENO_RE.sub("", title).rstrip("\t ").strip()


def _has_toc_field(para) -> bool:
    """段落是否含 TOC 域代码（w:instrText 含 'TOC'）。"""
    xml = para._p.xml
    return "instrText" in xml and "TOC" in xml


def _is_toc_para(para, style_name: str) -> bool:
    """目录段落判定（三特征可组合命中其一即跳过）。"""
    if style_name and _TOC_STYLE_RE.match(style_name):
        return True
    if _TAB_PAGENO_RE.search(para.text):
        return True
    try:
        if _has_toc_field(para):
            return True
    except Exception:
        pass
    return False


class TemplateOutlineError(Exception):
    """模板章节解析失败（路由据此返回 422）。"""


def _style_name_of(para) -> str:
    try:
        style = getattr(para, "style", None)
        return ((style.name if style else "") or "").strip()
    except Exception:
        return ""


def _para_level(para, text_fallback: bool = True, style_name: str = "") -> int:
    """0 = 正文段落；1-4 = 标题层级。样式优先；text_fallback=True 时启用文本模式兜底。"""
    m = _HEADING_STYLE_RE.match(style_name or _style_name_of(para))
    if m:
        return int(m.group(2))
    if not text_fallback:
        return 0
    text = para.text.strip()
    if not text or len(text) > 60:
        return 0
    if _CHAPTER_RE.match(text):
        return 1
    if _SECTION_RE.match(text):
        return 2
    if _SUBSECTION_RE.match(text):
        return 3
    m = _NUMBERED_RE.match(text)
    if m:
        return min(m.group(1).count(".") + 1, 4)
    return 0


def _scan(docx_path: str) -> list:
    """扫描 docx，返回有序条目：("h", level, title) 标题 / ("p", 0, chars) 正文段字数。

    目录（TOC）段落整体跳过（不计标题、不计字数）；保留标题防御性剥离尾部 \\t页码。
    文档含 Heading 样式标题时仅按样式识别（避免文本模式误收正文长句）；
    全文无 Heading 样式（样式不规范）时才启用文本模式兜底。
    """
    from docx import Document
    document = Document(docx_path)
    paras = []
    for para in document.paragraphs:
        style_name = _style_name_of(para)
        if _is_toc_para(para, style_name):
            continue
        paras.append((para, style_name))
    # 存在样式标题 → 仅按样式判定；否则文本模式兜底
    has_heading_style = any(_HEADING_STYLE_RE.match(sn) for _, sn in paras)
    items = []
    for para, style_name in paras:
        level = _para_level(para, text_fallback=not has_heading_style, style_name=style_name)
        if level:
            title = _strip_tab_pageno(para.text)
            if title:
                items.append(("h", level, title))
        else:
            chars = len(_WS_RE.sub("", para.text))
            if chars:
                items.append(("p", 0, chars))
    return items


def _headings(items: list) -> list:
    """[(index_in_items, level, title)]，仅标题条目。"""
    return [(i, lvl, t) for i, (kind, lvl, t) in enumerate(items) if kind == "h" and t]


def _section_span_chars(items: list, headings: list, hi: int) -> int:
    """第 hi 个标题的正文字数：从标题后到下一同级/更高级标题前的所有正文段。"""
    idx, level, _ = headings[hi]
    end = len(items)
    for j in range(hi + 1, len(headings)):
        if headings[j][1] <= level:
            end = headings[j][0]
            break
    return sum(chars for kind, _, chars in items[idx + 1:end] if kind == "p")


def parse_outline(docx_path: str) -> list:
    """解析模板 docx 章节树，返回 [(level, title)]（文档顺序，level 1-4）。

    无标题结构或非 docx 时抛 TemplateOutlineError。
    """
    p = Path(docx_path)
    if p.suffix.lower() != ".docx":
        raise TemplateOutlineError("仅支持 docx 模板解析章节结构")
    try:
        items = _scan(docx_path)
    except Exception as exc:
        raise TemplateOutlineError(f"模板解析失败：{exc}") from exc
    outline = [(lvl, t) for _, lvl, t in _headings(items)]
    if not outline:
        raise TemplateOutlineError("模板中未识别到章节标题，请检查模板样式")
    return outline


def build_tree(outline: list) -> list:
    """把 [(level, title)] 扁平列表组装为 replace_sections 所需的嵌套树（层级按深度归一化）。"""
    roots = []
    stack = []  # (level, node)
    for level, title in outline:
        while stack and stack[-1][0] >= level:
            stack.pop()
        node = {"title": title, "level": len(stack) + 1, "children": []}
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            roots.append(node)
        stack.append((level, node))
    return roots


def _titles_match(template_title: str, target: str) -> bool:
    a = _WS_RE.sub("", template_title)
    b = _WS_RE.sub("", target)
    return bool(a == b or (b and b in a) or (a and a in b))


def section_target_chars(docx_path: str, title: str, level: "int | None" = None) -> int:
    """模板中 title 章节的正文实测字数；找不到时同级平均→全体平均→3000。"""
    try:
        items = _scan(docx_path)
    except Exception:
        return DEFAULT_TARGET_CHARS
    headings = _headings(items)
    if not headings:
        return DEFAULT_TARGET_CHARS
    for hi, (_, lvl, t) in enumerate(headings):
        if _titles_match(t, title):
            chars = _section_span_chars(items, headings, hi)
            return chars if chars > 0 else DEFAULT_TARGET_CHARS
    # 未找到对应章节：优先同级章节平均，再退全体章节平均，最后默认 3000
    pool = None
    if level:
        pool = [_section_span_chars(items, headings, hi)
                for hi, (_, lvl, _) in enumerate(headings) if lvl == level]
        pool = [c for c in pool if c > 0]
    if not pool:
        pool = [c for c in (_section_span_chars(items, headings, hi)
                            for hi in range(len(headings))) if c > 0]
    if not pool:
        return DEFAULT_TARGET_CHARS
    return max(int(sum(pool) / len(pool)), 1)


def para_heading_level(para) -> int:
    """标题层级判定（0=正文）：样式优先（Heading/标题 1-4），无样式命中时
    文本模式兜底（第X章/X、/（X）/数字编号，≤60 字）。TOC 段落恒返回 0。
    供商务标底稿裁切复用；与既有 _para_level 不同：无条件启用文本兜底
    （裁切场景面对样式不规范的招标文件原文）。"""
    style_name = _style_name_of(para)
    if _is_toc_para(para, style_name):
        return 0
    return _para_level(para, text_fallback=True, style_name=style_name)
