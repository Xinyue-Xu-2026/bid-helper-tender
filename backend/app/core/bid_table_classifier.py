"""底稿表格角色建议：按表头行关键词签名匹配，产出待用户确认的绑定建议。
只建议、不静默填充；拿不准一律 ignore。

bindings JSON schema（本模块为权威定义，T7 导出与 T9 存储/回显均按此实现）：
```json
{
  "tables": [
    {
      "table_index": 0,
      "role": "person_roster",
      "columns": {"seq": 0, "name": 1, "title": 2, "work_years": 3, "certs": 4},
      "person_scope": "all",
      "perf_scope": "all",
      "label_kind": "",
      "person": "",
      "confirmed": false
    }
  ],
  "swap_toc": false
}
```
- role ∈ person_roster | lead_resume | perf_list | quote | image_slot | ignore
- columns：数据表 = {语义键: 列下标}；lead_resume = {标签文本: 语义键}（键值表）
- person_scope ∈ all | lead | members（仅 person_roster）；
  perf_scope ∈ all | lead | section1 | section2（仅 perf_list）
- image_slot 专用：label_kind ∈ 职称证书 | 社保 | 身份证 | 注册证书；
  person = "lead" 或 "member:N"（非负责人序号，0 起）
- confirmed：用户确认置 true；导出只填充 confirmed=true 且 role≠ignore 的表
  （本模块产出的建议 confirmed 恒 false）

分类规则（按序判定，先中先得）：
1. 表格仅 1 列 → image_slot；label_kind 按首行文本命中 IMAGE_LABEL_KINDS
   首个关键词（元组内 (子串, 语义)），全不中留空；confidence 高（命中）/ 低。
2. 前 2 行任一单元格含 QUOTE_KEYWORDS 任一关键词 → quote。
3. 表头行 = 第 0 行；若第 0 行整行关键词命中数 < 2 且表格行数 ≥ 2 →
   用"第 0 行 + 第 1 行同列文本拼接"重试（跨行表头兜底）。
   逐列匹配 PERSON_COL_KEYWORDS / PERF_COL_KEYWORDS：子串匹配（去空白后），
   长关键词优先，每列只取一个语义、每语义只占一列（先匹配成功的语义锁定该列）。
   注意 label 语义键代表"人员安排/岗位/职务"列（职务栏），role 语义键代表
   "拟派岗位"列——两者关键词不可混淆（label 关键词不含"拟派/本岗位"）。
4. person 命中数 ≥ 2 且 ≥ perf 命中数 → person_roster；否则 perf 命中数 ≥ 2
   → perf_list。confidence：命中 ≥ 3 → 高，2 → 低。
5. 表格 2~3 列且第 0 列逐行（数据行文本）命中 RESUME_LABELS ≥ 3 个不同标签
   → lead_resume；columns = {标签原文: 语义键}（未入 RESUME_LABEL_TO_SEM
   的标签不进 columns）。confidence 高（≥5）/ 低。
6. 其余 → ignore（confidence 低）。

合并单元格：row.cells 对横向合并重复同一 _tc；逐列记录按 _tc 引用去重
（同一 _tc 只取首次列位），保证 columns 下标为网格列坐标系（与后续
填充写入坐标一致）。
"""
import re

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core.template_outline import para_heading_level

ROLES = ("person_roster", "lead_resume", "perf_list", "quote", "image_slot", "ignore")

PERSON_COL_KEYWORDS = {
    "seq": ("序号",), "label": ("人员安排", "岗位", "职务"),
    "name": ("姓名",), "gender": ("性别",), "age": ("年龄",),
    "education": ("学历",), "title": ("职称",),
    "work_years": ("专业工作年限", "工作年限", "从业年限"),
    "certs": ("执业资格", "注册资格", "资格证书", "资格"),
    "role": ("拟派岗位", "拟任职务", "本项目岗位"),
}
PERF_COL_KEYWORDS = {
    "seq": ("序号",), "project_name": ("项目名称",),
    "client": ("委托单位", "业主单位", "建设单位", "委托人"),
    "client_contact": ("联系方式",), "sign_date": ("合同签订", "签订时间", "签订日期"),
    "amount": ("合同金额", "工程造价", "金额"), "project_type": ("项目类型",),
    "service_type": ("服务类型",), "content": ("主要内容", "服务内容"),
    "proof_page": ("证明材料", "页码"),
}
QUOTE_KEYWORDS = ("报价", "费率", "折扣")
RESUME_LABELS = ("姓名", "性别", "年龄", "学历", "职称", "执业资格",
                 "身份证号", "工作经历", "已完项目", "类似业绩")
RESUME_LABEL_TO_SEM = {"姓名": "name", "性别": "gender", "年龄": "age",
                       "学历": "education", "职称": "title", "执业资格": "certs",
                       "身份证号": "id_no", "已完项目": "lead_perfs",
                       "类似业绩": "lead_perfs"}
IMAGE_LABEL_KINDS = (("社保", "社保"), ("身份证", "身份证"),
                     ("职称证书", "职称证书"), ("注册证书", "注册证书"),
                     ("资格证书", "注册证书"), ("执业资格", "注册证书"))

_WS_RE = re.compile(r"\s+")


def _norm(s: str) -> str:
    """去全部空白。"""
    return _WS_RE.sub("", s or "")


def _iter_block_items(doc):
    """按 body 顺序产出 Paragraph / Table（同 bid_template_exporter 的块遍历手法）。"""
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def _dedup_col_texts(row) -> list:
    """行内单元格按 _tc 引用去重（横向合并同一 _tc 只取首次列位），
    返回 [(网格列下标, 原始文本)]，保位置映射。"""
    seen = []
    pairs = []
    for idx, cell in enumerate(row.cells):
        tc = cell._tc
        if any(tc is t for t in seen):
            continue
        seen.append(tc)
        pairs.append((idx, cell.text))
    return pairs


def _header_cells(table) -> list:
    """首行单元格文本（横向合并去重，保位置映射）。"""
    if not table.rows:
        return []
    return [text.strip() for _, text in _dedup_col_texts(table.rows[0])]


def _all_keywords():
    for table in (PERSON_COL_KEYWORDS, PERF_COL_KEYWORDS):
        for kws in table.values():
            yield from kws


def _row_hit_count(pairs) -> int:
    """行内（已去重）命中任一人员/业绩关键词的列数。"""
    kws = tuple(_all_keywords())
    return sum(1 for _, text in pairs
               if any(kw in _norm(text) for kw in kws))


def _match_columns(pairs) -> tuple:
    """逐列匹配人员/业绩语义：子串匹配（去空白后），长关键词优先，
    每列只取一个语义、每语义只占一列。返回 (person_map, perf_map)：
    {语义键: 网格列下标}。"""
    candidates = []  # (-关键词长度, 列下标, family 序, family, 语义键)
    # family 序：同列同长关键词竞争时人员族优先于业绩族（如共有的"序号"）
    for family_order, family, table in (
            (0, "person", PERSON_COL_KEYWORDS), (1, "perf", PERF_COL_KEYWORDS)):
        for sem, kws in table.items():
            for kw in kws:
                for col_idx, text in pairs:
                    if kw in _norm(text):
                        candidates.append(
                            (-len(kw), col_idx, family_order, family, sem))
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    person_map, perf_map = {}, {}
    used_cols = set()
    for _, col_idx, _, family, sem in candidates:
        if col_idx in used_cols:
            continue
        mapping = person_map if family == "person" else perf_map
        if sem in mapping:
            continue
        mapping[sem] = col_idx
        used_cols.add(col_idx)
    return person_map, perf_map


def _is_quote(table) -> bool:
    """前 2 行任一单元格含报价关键词。"""
    for row in table.rows[:2]:
        for cell in row.cells:
            text = _norm(cell.text)
            if any(kw in text for kw in QUOTE_KEYWORDS):
                return True
    return False


def _match_resume(table) -> dict:
    """第 0 列逐行命中 RESUME_LABELS，返回 {标签原文: 语义键}
    （未入 RESUME_LABEL_TO_SEM 的标签只计数不进映射）及命中数。"""
    hits = set()
    columns = {}
    for row in table.rows:
        pairs = _dedup_col_texts(row)
        if not pairs:
            continue
        text = _norm(pairs[0][1])
        for label in RESUME_LABELS:
            if label in text:
                hits.add(label)
                if label in RESUME_LABEL_TO_SEM:
                    columns[label] = RESUME_LABEL_TO_SEM[label]
    return hits, columns


def _image_label_kind(table) -> str:
    """图片占位表首行文本命中 IMAGE_LABEL_KINDS 首个关键词的语义，全不中留空。"""
    first = _norm(table.rows[0].cells[0].text) if table.rows else ""
    for sub, sem in IMAGE_LABEL_KINDS:
        if sub in first:
            return sem
    return ""


def _is_members_heading(heading: str) -> bool:
    return ("项目组" in heading) or ("其他人员" in heading)


def _classify_table(table, table_index: int, heading: str,
                    current_member: int) -> dict:
    item = {
        "table_index": table_index,
        "header": _header_cells(table),
        "role": "ignore",
        "columns": {},
        "person_scope": "",
        "perf_scope": "",
        "label_kind": "",
        "person": "",
        "confidence": "低",
        "context_heading": heading,
        "confirmed": False,
    }
    rows = table.rows
    if not rows:
        return item

    # 规则 1：仅 1 列 → image_slot
    if len(table.columns) == 1:
        item["role"] = "image_slot"
        item["label_kind"] = _image_label_kind(table)
        item["confidence"] = "高" if item["label_kind"] else "低"
        if "负责人" in heading:
            item["person"] = "lead"
        elif _is_members_heading(heading):
            item["person"] = f"member:{current_member}"
        return item

    # 规则 2：前 2 行任一单元格含报价关键词 → quote
    if _is_quote(table):
        item["role"] = "quote"
        item["confidence"] = "高"
        return item

    # 规则 3：表头行关键词签名（第 0 行命中 < 2 且行数 ≥ 2 时跨行拼接兜底）
    pairs = _dedup_col_texts(rows[0])
    if _row_hit_count(pairs) < 2 and len(rows) >= 2:
        row1 = dict(_dedup_col_texts(rows[1]))
        pairs = [(idx, (text or "") + (row1.get(idx) or ""))
                 for idx, text in pairs]
    person_map, perf_map = _match_columns(pairs)

    # 规则 4：命中数判定人员表 / 业绩表
    if len(person_map) >= 2 and len(person_map) >= len(perf_map):
        item["role"] = "person_roster"
        item["columns"] = person_map
        item["confidence"] = "高" if len(person_map) >= 3 else "低"
        if "负责人" in heading:
            item["person_scope"] = "lead"
        elif _is_members_heading(heading):
            item["person_scope"] = "members"
        else:
            item["person_scope"] = "all"
        return item
    if len(perf_map) >= 2:
        item["role"] = "perf_list"
        item["columns"] = perf_map
        item["confidence"] = "高" if len(perf_map) >= 3 else "低"
        item["perf_scope"] = "lead" if "负责人" in heading else "all"
        return item

    # 规则 5：2~3 列且第 0 列逐行命中简历标签 ≥ 3 → lead_resume
    if 2 <= len(table.columns) <= 3:
        hits, columns = _match_resume(table)
        if len(hits) >= 3:
            item["role"] = "lead_resume"
            item["columns"] = columns
            item["confidence"] = "高" if len(hits) >= 5 else "低"
            return item

    # 规则 6：拿不准一律 ignore
    return item


def classify_tables(docx_path: str) -> list:
    """扫描底稿 docx 全部表格，按表头关键词签名产出绑定建议列表。

    每项：{"table_index", "header", "role", "columns", "person_scope",
    "perf_scope", "label_kind", "person", "confidence", "context_heading",
    "confirmed"}；confirmed 恒 false（待用户确认）。

    上下文建议：遍历时维护最近标题文本（块遍历，标题用 para_heading_level）；
    标题含"负责人"→ person_roster.person_scope="lead"、image_slot.person="lead"、
    perf_list.perf_scope="lead"；含"项目组"/"其他人员"→ person_scope="members"、
    成员序号随"其他人员"标题递增（image_slot.person 依次 member:0, member:1,...）。
    """
    doc = Document(docx_path)
    results = []
    heading = ""
    member_counter = 0
    current_member = 0
    table_index = 0
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            if para_heading_level(block):
                text = block.text.strip()
                if text:
                    heading = text
                    if "其他人员" in text:
                        current_member = member_counter
                        member_counter += 1
        else:  # Table
            results.append(_classify_table(
                block, table_index, heading, current_member))
            table_index += 1
    return results
