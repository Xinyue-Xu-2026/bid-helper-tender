"""导出产物页面设置：宏信天德参考页眉/页脚包级移植 + 分节页码。

页眉（logo/绿字/绿线）与页脚（居中 PAGE 域）逐字节拷自参考包
（config.BID_HEADER_SOURCE_PATH，data/商务标页眉参考.docx），产物的
section 挂 headerReference/footerReference 指向移植 part——不手写
anchor XML，样式 100% 与参考一致。产物已有页眉/页脚引用一律替换为
参考样式（一期结论：商务标页眉统一为宏信天德样式，不继承招标文件页眉）。

分节页码：封面与目录区（首个连续 toc 段组，含 swap_toc 插入的 TOC 域段，
目录区之前即封面）划为第一节，不挂引用（无页眉无页码）；正文节挂参考
页眉+PAGE 页脚，页码从 1 起（pgNumType start=1，正文首页为第 1 页）。
无 toc 段组（裁切范围不含封面/目录）→ 整篇一节挂页眉+页码。

实现：fill_draft 保存后对产物 zip 后置处理（注入 part + 改 document.xml /
document.xml.rels / [Content_Types].xml），参考文件缺失/无效 → 跳过不
报错（降级），不破坏导出。
"""
import re
import zipfile
from copy import deepcopy
from pathlib import Path

from lxml import etree

from app import config

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"

_HEADER_NAME = "header_hxtd.xml"
_FOOTER_NAME = "footer_hxtd.xml"
_HEADER_CT = ("application/vnd.openxmlformats-officedocument"
              ".wordprocessingml.header+xml")
_FOOTER_CT = ("application/vnd.openxmlformats-officedocument"
              ".wordprocessingml.footer+xml")
_IMAGE_CT = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
             "gif": "image/gif", "bmp": "image/bmp"}

# 参考包缺页脚时的兜底：居中 PAGE 域页脚（9pt）
_FOOTER_FALLBACK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr>'
    '<w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr>'
    '<w:fldChar w:fldCharType="begin"/>'
    '<w:instrText xml:space="preserve">PAGE \\* MERGEFORMAT</w:instrText>'
    '<w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>'
)


def _wq(ns, tag):
    return f"{{{ns}}}{tag}"


def _read_part(z, names, part):
    """读参考包内一个 part：xml + rels + rels 引用的图片媒体。"""
    if not part:
        return None
    base = part.rsplit("/", 1)[-1]
    rels_name = f"word/_rels/{base}.rels"
    rels_xml = z.read(rels_name) if rels_name in names else None
    media = {}
    if rels_xml:
        for rel in etree.fromstring(rels_xml):
            if (rel.get("Type") or "").endswith("/image"):
                tgt = rel.get("Target")
                media[tgt] = z.read(f"word/{tgt}")
    return {"xml": z.read(part), "rels_xml": rels_xml, "media": media}


def _load_reference(ref_path: Path):
    """读参考包：首个 header part 与首个 footer part（含 rels/媒体）。"""
    with zipfile.ZipFile(str(ref_path)) as z:
        names = z.namelist()

        def _pick(prefix):
            cands = sorted(n for n in names
                           if re.fullmatch(rf"word/{prefix}\d+\.xml", n))
            return cands[0] if cands else None

        header = _read_part(z, names, _pick("header"))
        footer = _read_part(z, names, _pick("footer"))
    if footer is None:
        footer = {"xml": _FOOTER_FALLBACK.encode("utf-8"),
                  "rels_xml": None, "media": {}}
    return {"header": header, "footer": footer}


def _is_toc_el(p_el) -> bool:
    """段落是否 toc（样式名 toc 开头，或段内含 TOC 域——swap_toc 插入的）。"""
    pPr = p_el.find(_wq(W, "pPr"))
    if pPr is not None:
        st = pPr.find(_wq(W, "pStyle"))
        if st is not None and (st.get(_wq(W, "val")) or "").lower().startswith("toc"):
            return True
    for instr in p_el.iter(_wq(W, "instrText")):
        if instr.text and "TOC" in instr.text:
            return True
    return False


_TOC_ENTRY_RE = re.compile(r".+?[\.\s·…]{2,}\s*\d{1,4}\s*$")


def _el_text(el) -> str:
    return "".join(t.text or "" for t in el.iter(_wq(W, "t")))


def is_static_toc_group(children) -> "int | None":
    """静态文本目录识别（V1.2 7.5）：「目录」标题段 + 其后连续 ≥2 个
    「章节名…页码」形态段（双重特征缺一不可，防正文"目录"字样误判），
    返回目录组末元素下标；否则 None。"""
    for i, el in enumerate(children):
        if el.tag != _wq(W, "p"):
            continue
        title = _el_text(el).strip()
        if not title.startswith("目录"):
            continue
        end, count, j = i, 0, i + 1
        while (j < len(children) and children[j].tag == _wq(W, "p")
               and _TOC_ENTRY_RE.match(_el_text(children[j]).strip())):
            end, count, j = j, count + 1, j + 1
        if count >= 2:
            return end
    return None


def _para_jc(p_el) -> str:
    pPr = p_el.find(_wq(W, "pPr"))
    if pPr is None:
        return ""
    jc = pPr.find(_wq(W, "jc"))
    return (jc.get(_wq(W, "val")) or "") if jc is not None else ""


def check_footer_page_centered(docx_path: str) -> list:
    """断言产物各 footer part 中 PAGE 域所在段落居中（jc=center）。
    段落缺 jc（未显式设置）→ 安全补 center 后复检（幂等）；显式非居中
    （有意设置）→ 不静默改，记告警。返回告警列表（空=通过）。"""
    warnings = []
    path = Path(docx_path)
    with zipfile.ZipFile(str(path)) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    footer_names = sorted(n for n in entries
                          if re.fullmatch(r"word/footer[^/]*\.xml", n))
    changed = False
    for name in footer_names:
        root = etree.fromstring(entries[name])
        for idx, p in enumerate(root.iter(_wq(W, "p"))):
            if not any("PAGE" in (instr.text or "")
                       for instr in p.iter(_wq(W, "instrText"))):
                continue
            jc = _para_jc(p)
            if jc == "center":
                continue
            if jc:
                # 显式非居中：有意设置，不静默改，告警
                warnings.append(
                    f"{name} 段落[{idx}] PAGE 域段落未居中（jc={jc}）")
                continue
            # 缺 jc：补 center（写回产物）后复检
            pPr = p.find(_wq(W, "pPr"))
            if pPr is None:
                pPr = etree.Element(_wq(W, "pPr"))
                p.insert(0, pPr)
            jc_el = etree.SubElement(pPr, _wq(W, "jc"))
            jc_el.set(_wq(W, "val"), "center")
            changed = True
            if _para_jc(p) != "center":
                warnings.append(f"{name} 段落[{idx}] PAGE 域段落未居中")
        entries[name] = etree.tostring(root, xml_declaration=True,
                                       encoding="UTF-8", standalone=True)
    if changed:
        tmp = path.with_suffix(".jctmp")
        with zipfile.ZipFile(str(tmp), "w", zipfile.ZIP_DEFLATED) as z:
            for n, data in entries.items():
                z.writestr(n, data)
        tmp.replace(path)
    return warnings


def _clean_sectpr(sp) -> None:
    """去掉 sectPr 的页眉/页脚引用与首页不同/页码设置（统一为参考样式）。"""
    for tag in ("headerReference", "footerReference", "titlePg", "pgNumType"):
        for el in sp.findall(_wq(W, tag)):
            sp.remove(el)


def _attach_refs(sp, header_rid, footer_rid, restart_page=False) -> None:
    """给 sectPr 挂参考页眉/页脚引用（引用须为 sectPr 最前子元素）。"""
    _clean_sectpr(sp)
    if footer_rid:
        fel = etree.Element(_wq(W, "footerReference"))
        fel.set(_wq(W, "type"), "default")
        fel.set(_wq(R, "id"), footer_rid)
        sp.insert(0, fel)
    if header_rid:
        hel = etree.Element(_wq(W, "headerReference"))
        hel.set(_wq(W, "type"), "default")
        hel.set(_wq(R, "id"), header_rid)
        sp.insert(0, hel)
    if restart_page:
        pg = etree.Element(_wq(W, "pgNumType"))
        pg.set(_wq(W, "start"), "1")
        # CT_SectPr 序列：pgNumType 须在 cols/formProt/vAlign/noEndnote/
        # titlePg/textDirection/bidi/rtlGutter/docGrid/printerSettings 之前
        after_tags = {_wq(W, t) for t in (
            "cols", "formProt", "vAlign", "noEndnote", "titlePg",
            "textDirection", "bidi", "rtlGutter", "docGrid",
            "printerSettings", "sectPrChange")}
        anchor = next((c for c in sp if c.tag in after_tags), None)
        if anchor is not None:
            anchor.addprevious(pg)
        else:
            sp.append(pg)


def apply_page_setup(docx_path: str) -> dict:
    """对导出产物做页眉/页脚移植与分节页码（zip 后置处理）。
    返回 {"header_applied": bool, "page_numbers": bool, "degraded": str,
          "sections": int, "section_page_numbers": [bool], "warnings": [str]}。
    sections = document.xml 中 sectPr 数；section_page_numbers 逐节标记
    「挂页脚引用且页码重起」；warnings 含页脚 PAGE 域居中断言结果。"""
    result = {"header_applied": False, "page_numbers": False, "degraded": "",
              "sections": 1, "section_page_numbers": [], "warnings": []}
    ref = Path(config.BID_HEADER_SOURCE_PATH)
    if not ref.exists():
        result["degraded"] = "页眉参考文件缺失，已跳过页眉/页码设置"
        return result
    try:
        parts = _load_reference(ref)
    except Exception:
        parts = None
    if not parts or not parts["header"]:
        result["degraded"] = "页眉参考文件无效，已跳过页眉/页码设置"
        return result

    path = Path(docx_path)
    with zipfile.ZipFile(str(path)) as z:
        entries = {n: z.read(n) for n in z.namelist()}

    # ---- document.xml：分节 + 挂引用 ----
    doc_xml = etree.fromstring(entries["word/document.xml"])
    body = doc_xml.find(_wq(W, "body"))
    children = list(body)
    body_sectPr = body.find(_wq(W, "sectPr"))
    if body_sectPr is None:
        body_sectPr = etree.SubElement(body, _wq(W, "sectPr"))
        children = list(body)

    # 首个连续目录段组（封面+目录区）：优先静态文本目录（「目录」标题+
    # 页码形态段组，V1.2 7.5），无则回退 toc 样式/TOC 域组（旧行为）
    split_after = None
    static_end = is_static_toc_group(children)
    if static_end is not None and any(
            el.tag != _wq(W, "sectPr") for el in children[static_end + 1:]):
        split_after = static_end
    if split_after is None:
        toc_idx = [i for i, el in enumerate(children)
                   if el.tag == _wq(W, "p") and _is_toc_el(el)]
        if toc_idx:
            group_end = toc_idx[0]
            for i in toc_idx[1:]:
                if i == group_end + 1:
                    group_end = i
                else:
                    break
            # 组后还有正文内容（body sectPr 之外的元素）才需要拆节
            if any(el.tag != _wq(W, "sectPr") for el in children[group_end + 1:]):
                split_after = group_end

    # 新 rId
    rels_root = etree.fromstring(entries["word/_rels/document.xml.rels"])
    existing_ids = {rel.get("Id") for rel in rels_root}

    def _new_rid():
        n = 9000
        while f"rId{n}" in existing_ids:
            n += 1
        rid = f"rId{n}"
        existing_ids.add(rid)
        return rid

    header_rid = _new_rid()
    footer_rid = _new_rid()

    split_p = None
    sect1 = None
    if split_after is not None:
        # 节1 = 封面+目录（children[:split_after+1]）：干净 sectPr（无引用）
        sect1 = deepcopy(body_sectPr)
        _clean_sectpr(sect1)
        split_p = etree.Element(_wq(W, "p"))
        pPr = etree.SubElement(split_p, _wq(W, "pPr"))
        pPr.append(sect1)
        children[split_after].addnext(split_p)

    # 逐 sectPr 处理：分节段之前（节1）只清理；其后（含 body sectPr）挂参考引用
    past_split = split_p is None
    for el in body.iter():
        if el is split_p:
            past_split = True
            continue
        if el.tag != _wq(W, "sectPr") or el is sect1:
            continue
        if el is body_sectPr:
            _attach_refs(el, header_rid, footer_rid,
                         restart_page=split_p is not None)
        elif past_split:
            _attach_refs(el, header_rid, footer_rid)
        else:
            _clean_sectpr(el)

    # ---- rels：挂接移植 part ----
    for rid, typ, target in (
            (header_rid, "header", _HEADER_NAME),
            (footer_rid, "footer", _FOOTER_NAME)):
        rel = etree.SubElement(rels_root, _wq(PR, "Relationship"))
        rel.set("Id", rid)
        rel.set("Type", f"http://schemas.openxmlformats.org/officeDocument"
                        f"/2006/relationships/{typ}")
        rel.set("Target", target)

    # ---- 移植 part 与媒体（媒体重命名 hxtd_ 前缀防冲突）----
    media_exts = set()
    for part, part_name in ((parts["header"], _HEADER_NAME),
                            (parts["footer"], _FOOTER_NAME)):
        rename = {}
        for tgt in part["media"]:
            base = tgt.rsplit("/", 1)[-1]
            rename[tgt] = f"media/hxtd_{base}"
            ext = base.rsplit(".", 1)[-1].lower() if "." in base else "png"
            media_exts.add(ext)
        entries[f"word/{part_name}"] = part["xml"]
        if part["rels_xml"]:
            rels_part = etree.fromstring(part["rels_xml"])
            for rel in rels_part:
                tgt = rel.get("Target")
                if tgt in rename:
                    rel.set("Target", rename[tgt])
            entries[f"word/_rels/{part_name}.rels"] = etree.tostring(
                rels_part, xml_declaration=True, encoding="UTF-8",
                standalone=True)
        for tgt, data in part["media"].items():
            entries[f"word/{rename[tgt]}"] = data

    # ---- [Content_Types].xml ----
    ct_root = etree.fromstring(entries["[Content_Types].xml"])
    overrides = {el.get("PartName")
                 for el in ct_root.findall(_wq(CT, "Override"))}
    for part_name, ct in ((_HEADER_NAME, _HEADER_CT),
                          (_FOOTER_NAME, _FOOTER_CT)):
        if f"/word/{part_name}" not in overrides:
            el = etree.SubElement(ct_root, _wq(CT, "Override"))
            el.set("PartName", f"/word/{part_name}")
            el.set("ContentType", ct)
    defaults = {el.get("Extension").lower()
                for el in ct_root.findall(_wq(CT, "Default"))}
    for ext in media_exts:
        if ext not in defaults:
            el = etree.SubElement(ct_root, _wq(CT, "Default"))
            el.set("Extension", ext)
            el.set("ContentType", _IMAGE_CT.get(ext, "image/png"))

    entries["word/document.xml"] = etree.tostring(
        doc_xml, xml_declaration=True, encoding="UTF-8", standalone=True)
    entries["word/_rels/document.xml.rels"] = etree.tostring(
        rels_root, xml_declaration=True, encoding="UTF-8", standalone=True)
    entries["[Content_Types].xml"] = etree.tostring(
        ct_root, xml_declaration=True, encoding="UTF-8", standalone=True)

    tmp = path.with_suffix(".p2tmp")
    with zipfile.ZipFile(str(tmp), "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    tmp.replace(path)

    # 分节报告 + 页脚 PAGE 域居中断言（缺 jc 自动补，显式非居中告警）
    sects = [el for el in body.iter() if el.tag == _wq(W, "sectPr")]
    result["sections"] = len(sects)
    result["section_page_numbers"] = [
        bool(sp.findall(_wq(W, "footerReference")))
        and sp.find(_wq(W, "pgNumType")) is not None
        for sp in sects]
    result["warnings"] = check_footer_page_centered(str(path))

    result["header_applied"] = True
    result["page_numbers"] = True
    return result
