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
import re

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Cm
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


# 注册证书类占位标签关键词（职业资格证书/注册证书都算注册证书类）
_CERT_IMAGE_KEYWORDS = ("注册证书", "职业资格证书", "资格证书")


def _clear_table_images(table: Table) -> None:
    """清除占位表数据行里已存在的图片（模板是上一次投标填过的文档，会残留旧扫描件）。"""
    for row in table.rows[1:]:
        cell = row.cells[0]
        for dr in list(cell._tc.iter(qn("w:drawing"))):
            dr.getparent().remove(dr)


def _insert_image_into_table(table: Table, image_path: str) -> None:
    """往图片占位表（1列，首行是标签文字）插入图片。无文件/路径无效则跳过。"""
    if not image_path or not Path(image_path).exists():
        return
    row = table.rows[1] if len(table.rows) > 1 else table.rows[0]
    cell = row.cells[0]
    para = cell.paragraphs[0] if cell.paragraphs else cell.add_paragraph()
    para.add_run().add_picture(image_path, width=Cm(8))


def _insert_person_images(doc, persons) -> None:
    """按人员顺序把图片插入「三、人员配备表」的占位表（1列，首行含标签文字）。
    persons 已是负责人优先排序：[{name, fields, is_lead}]。"""
    if not persons:
        return
    person_images = []
    for p in persons:
        f = p.get("fields") or {}
        certs = [c for c in (f.get("证书") or []) if isinstance(c, dict)]
        person_images.append({
            "职称证书": f.get("职称证书扫描件") or "",
            "社保": f.get("社保缴纳证明扫描件") or "",
            "certs": [c.get("扫描件") or "" for c in certs],
        })

    in_section3 = False
    sub = ""          # "" / "lead" / "members"
    cur_person = None  # person_images 下标
    member_idx = 0
    cert_slot = 0

    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            level = _heading_level(block)
            if not level:
                continue
            text = block.text.strip()
            if level == 1:
                if text.startswith("三、人员配备表"):
                    in_section3, sub, cur_person = True, "", None
                elif text.startswith("四、"):
                    in_section3 = False
                else:
                    in_section3 = False
            elif in_section3 and level == 2:
                if text.startswith("2、项目负责人"):
                    sub, cur_person, cert_slot = "lead", 0, 0
                elif text.startswith("3、项目组人员"):
                    sub, cur_person, member_idx, cert_slot = "members", None, 0, 0
                else:
                    sub = ""
            elif in_section3 and level == 3:
                if sub == "members" and "项目组其他人员" in text:
                    cur_person = 1 + member_idx
                    member_idx += 1
                    cert_slot = 0
        else:  # Table
            if not in_section3 or cur_person is None:
                continue
            if len(block.columns) != 1:      # 只处理 1 列图片占位表
                continue
            label = (block.rows[0].cells[0].text or "").strip()
            # 先清掉占位表里残留的旧扫描件（模板为上次投标填过的文档）
            _clear_table_images(block)
            if cur_person >= len(person_images):
                continue
            pi = person_images[cur_person]
            if "职称证书" in label:
                _insert_image_into_table(block, pi["职称证书"])
            elif "社保" in label:
                _insert_image_into_table(block, pi["社保"])
            elif any(k in label for k in _CERT_IMAGE_KEYWORDS):
                if cert_slot < len(pi["certs"]):
                    _insert_image_into_table(block, pi["certs"][cert_slot])
                    cert_slot += 1


# ---------- 残留文本替换（项目编号/项目名称/日期）与人员子标题改名 ----------
#
# 模板残留格式（以 data/商务标模板.docx 实测为准）：
# - 项目编号：封面「编       号：YZGKWD-2026-009号」、商务条款响应表
#   「项目编号：YZGKWD-2026-009号」、开标一览表单元格裸值「YZGKWD-2026-009号」，
#   共同子串为编号本体（含尾字「号」）。
# - 项目名称：封面「项 目 名 称：×××」（字间有空格）、正文「项目名称：×××」、
#   人员承诺书正文裸名「本单位参与本次 ×××项目投标活动」、开标一览表单元格裸值。
#   运行时先从带「项目名称」标签的段落中提取旧名，再全局替换该子串。
# - 日期：封面「日      期 ：2026年8月11日」、各表页脚「日 期：\t2026年8月11日」、
#   承诺函「日期：2026年8月11日」「日期:2026年8月11日」等变体，统一用
#   「日\s*期\s*[：:]」标签定位，仅替换其后的 Y年M月D日。
# - 目录（toc 样式段落）整段跳过，上述替换一律不触碰。

_PROJECT_NO_RE = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+号")
_PROJECT_NAME_LABEL_RE = re.compile(r"项\s*目\s*名\s*称\s*[：:]\s*(\S+)")
_DOC_DATE_RE = re.compile(
    r"(日\s*期\s*[：:]\s*)\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
_MEMBER_HEADING_RE = re.compile(r"^（\d+）项目组其他人员-")


def _iter_cell_paragraphs(cell):
    for para in cell.paragraphs:
        yield para
    for table in cell.tables:
        for row in table.rows:
            for sub in row.cells:
                yield from _iter_cell_paragraphs(sub)


def _iter_all_paragraphs(doc):
    """正文段落 + 所有表格（含嵌套）单元格内段落。"""
    for para in doc.paragraphs:
        yield para
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_cell_paragraphs(cell)


def _is_toc_paragraph(para: Paragraph) -> bool:
    style = para.style
    name = (style.name if style is not None else "") or ""
    return name.lower().startswith("toc")


def _para_text(para: Paragraph) -> str:
    return "".join(r.text for r in para.runs)


def _rewrite_paragraph_text(para: Paragraph, text: str) -> None:
    """整段改写：保留首个 run 的格式，删除其余 run。"""
    runs = para.runs
    if runs:
        runs[0].text = text
        for r in runs[1:]:
            r._element.getparent().remove(r._element)
    else:
        para.add_run(text)


def _replace_in_paragraph(para: Paragraph, pattern, repl) -> bool:
    """对段落整体文本做正则替换；命中时以首 run 格式重写整段。"""
    full = _para_text(para)
    if not full:
        return False
    new, count = pattern.subn(repl, full)
    if not count:
        return False
    _rewrite_paragraph_text(para, new)
    return True


def _discover_stale_values(doc) -> tuple:
    """从模板中提取残留的项目编号与项目名称（带标签的首个命中）。"""
    stale_no = ""
    stale_name = ""
    for para in _iter_all_paragraphs(doc):
        text = _para_text(para).strip()
        if not text:
            continue
        if not stale_no:
            m = _PROJECT_NO_RE.search(text)
            if m:
                stale_no = m.group(0)
        if not stale_name:
            m = _PROJECT_NAME_LABEL_RE.search(text)
            if m:
                stale_name = m.group(1)
        if stale_no and stale_name:
            break
    return stale_no, stale_name


def compute_text_subs(doc, project_no: str = "", project_name: str = "",
                      doc_date: str = "") -> list:
    """计算残留文本替换规则 [(pattern, repl)]（含 stale 编号/名称运行时发现）。
    _replace_stale_text 调本函数再逐段应用；导出与防篡改校验（bid_verify）
    共用同一套规则，保证"导出改了什么"与"校验豁免什么"一致。"""
    subs = []
    stale_no, stale_name = _discover_stale_values(doc)
    if project_no and stale_no:
        new_no = project_no if project_no.endswith("号") else f"{project_no}号"
        subs.append((re.compile(re.escape(stale_no)), new_no))
    if project_name and stale_name and project_name != stale_name:
        subs.append((re.compile(re.escape(stale_name)), project_name))
    if doc_date:
        m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", doc_date)
        if m:
            y, mo, d = (int(g) for g in m.groups())
            date_text = f"{y}年{mo}月{d}日"
            subs.append((_DOC_DATE_RE, lambda match: match.group(1) + date_text))
    return subs


def _replace_stale_text(doc, project_no: str = "", project_name: str = "",
                        doc_date: str = "") -> None:
    """替换模板中残留的上次投标文本：规则由 compute_text_subs 统一计算，
    此处仅逐段（含表格单元格，跳过 toc 段）应用。project_no/doc_date 为空
    则跳过对应替换，project_name 为空则不替换。"""
    subs = compute_text_subs(doc, project_no, project_name, doc_date)
    if not subs:
        return
    for para in _iter_all_paragraphs(doc):
        if _is_toc_paragraph(para):
            continue
        for pattern, repl in subs:
            _replace_in_paragraph(para, pattern, repl)


def _rename_member_headings(doc, member_names: list) -> None:
    """H2「3、项目组人员」下 H3「（N）项目组其他人员-×××」的名字后缀
    按所选非负责人员顺序替换；多余标题/人员互不干扰。"""
    if not member_names:
        return
    in_members = False
    idx = 0
    for block in _iter_block_items(doc):
        if not isinstance(block, Paragraph):
            continue
        level = _heading_level(block)
        if not level:
            continue
        text = block.text.strip()
        if level == 1:
            in_members = False
        elif level == 2:
            in_members = text.startswith("3、项目组人员")
        elif level == 3 and in_members and _MEMBER_HEADING_RE.match(text):
            if idx >= len(member_names):
                break
            prefix = _MEMBER_HEADING_RE.match(text).group(0)
            _rewrite_paragraph_text(block, prefix + member_names[idx])
            idx += 1


def build_bid_docx_from_template(template_path: str, dest_path: str, data: dict) -> Path:
    """以模板为底稿填充七张表。data: {"a".."g": 各行列表}（assemble_bid_template_data 产出）。

    额外支持的 data 键：
    - persons: [{name, fields, is_lead}]（负责人优先排序），用于插图与人员子标题改名；
    - project_no / project_name / doc_date: 替换模板中残留的上次投标文本，
      project_no/doc_date 为空则跳过对应替换，project_name 为空则不替换。
    """
    doc = Document(template_path)
    tables = _locate_tables(doc)
    for role, rows in (data or {}).items():
        table = tables.get(role)
        if table is not None:
            _fill_table(table, rows or [])
    persons = (data or {}).get("persons") or []
    member_names = [str(p.get("name") or "") for p in persons if not p.get("is_lead")]
    _rename_member_headings(doc, member_names)
    _replace_stale_text(
        doc,
        project_no=str((data or {}).get("project_no") or "").strip(),
        project_name=str((data or {}).get("project_name") or "").strip(),
        doc_date=str((data or {}).get("doc_date") or "").strip(),
    )
    _insert_person_images(doc, persons)
    dest = Path(dest_path)
    doc.save(str(dest))
    return dest
