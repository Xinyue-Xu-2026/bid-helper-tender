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
- role ∈ person_roster | lead_resume | resume_each | perf_list | quote | image_slot | ignore
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
5. 键值简历样表（第 0 列逐行命中 RESUME_LABELS ≥3 个不同标签）：含
   「拟在本项目任职/主要工作经历/执业资格证书名称」任一 → resume_each
   （2~5 列或 ≥10 列大网格，V1.2 7.2/7.4）；否则 2~3 列或大网格 →
   lead_resume；columns = {标签原文: 语义键}（未入 RESUME_LABEL_TO_SEM
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

ROLES = ("person_roster", "lead_resume", "resume_each", "perf_list", "quote",
         "image_slot", "ignore")

PERSON_COL_KEYWORDS = {
    "seq": ("序号",), "label": ("人员安排", "岗位", "职务"),
    "name": ("姓名",), "gender": ("性别",), "age": ("年龄",),
    "education": ("学历",), "title": ("职称",),
    "work_years": ("专业工作年限", "工作年限", "从业年限"),
    "certs": ("执业资格", "注册资格", "资格证书", "资格"),
    "role": ("拟派岗位", "拟任职务", "本项目岗位", "本项目任职", "本项目职务"),
}
PERF_COL_KEYWORDS = {
    "seq": ("序号",), "project_name": ("项目名称",),
    "client": ("委托单位", "业主单位", "建设单位", "委托人", "项目单位"),
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
# 「一人一表」键值样表特征标记（V1.2 7.4）：命中任一 → resume_each（整表克隆）
RESUME_EACH_MARKERS = ("拟在本项目任职", "主要工作经历", "执业资格证书名称")
IMAGE_LABEL_KINDS = (("社保", "社保"), ("身份证", "身份证"),
                     ("职称证书", "职称证书"), ("注册证书", "注册证书"),
                     ("资格证书", "注册证书"), ("执业资格", "注册证书"))

_WS_RE = re.compile(r"\s+")
_DATA_HINT_RE = re.compile(r"\d")


def _norm(s: str) -> str:
    """去全部空白。"""
    return _WS_RE.sub("", s or "")


def _row_has_data_semantics(pairs) -> bool:
    """行含数据语义信号：任一单元格含数字（序号/金额/年限/日期等）。"""
    return any(_DATA_HINT_RE.search(text or "") for _, text in pairs)


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


def _shared_header_cells(pairs0, pairs1) -> int:
    """row1 与 row0 在同网格列、同（规范化后）非空文本的单元格数。
    断裂 vMerge 副表头信号：row1 重复 row0 的标签文本（真实底稿中
    两行表头的前几列各自 vMerge=restart，文本完全重复）。"""
    row1 = {idx: _norm(text) for idx, text in pairs1}
    return sum(1 for idx, text in pairs0
               if _norm(text) and _norm(text) == row1.get(idx))


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


def _iter_all_cell_texts(table):
    """产出表格全部单元格的规范化文本（横向合并按 _tc 去重）。"""
    for row in table.rows:
        for _, text in _dedup_col_texts(row):
            yield _norm(text)


def _has_resume_markers(table) -> bool:
    """全表任一单元格命中简历样表标记（子串）。简历样表的标签可能横向排布
    在任意列（如 姓名/年龄/执业资格证书…），故不限于第 0 列。"""
    texts = list(_iter_all_cell_texts(table))
    return any(any(m in t for m in RESUME_EACH_MARKERS) for t in texts)


def _match_resume_all(table) -> tuple:
    """全表扫描 RESUME_LABELS（不限于第 0 列），返回 (hits, columns)。
    简历样表的标签常分布在多列（姓名/年龄/学历/职称/执业资格… 键值排布）。"""
    hits = set()
    columns = {}
    for text in _iter_all_cell_texts(table):
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
        "header_rows": 1,
        "mode": "",
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

    # 规则 3：表头行关键词签名（第 0 行命中 < 2 且行数 ≥ 2 时跨行拼接兜底）。
    # header_rows：拼接兜底触发 → 2；row0 自身命中足够但 row1 在同列重复
    # row0 标签 ≥2 格（断裂 vMerge 副表头，真实底稿 17×10 人员汇总表回归）
    # → 2；row0 整行无数据语义（无数字/金额等）且 row1 也命中表头关键词
    # 签名 ≥2（双层表头各行皆含关键词，7.1 补强）→ 2；其余 → 1。
    pairs = _dedup_col_texts(rows[0])
    if _row_hit_count(pairs) < 2 and len(rows) >= 2:
        row1 = dict(_dedup_col_texts(rows[1]))
        pairs = [(idx, (text or "") + (row1.get(idx) or ""))
                 for idx, text in pairs]
        item["header_rows"] = 2
    elif len(rows) >= 2 and _shared_header_cells(
            pairs, _dedup_col_texts(rows[1])) >= 2:
        item["header_rows"] = 2
    elif (len(rows) >= 2 and not _row_has_data_semantics(pairs)
          and _row_hit_count(_dedup_col_texts(rows[1])) >= 2):
        item["header_rows"] = 2
    person_map, perf_map = _match_columns(pairs)

    # 规则 3.5：简历样表优先识别（V1.2 修复）。简历样表表头含 姓名/年龄/
    # 执业资格 等关键词，会被下方 person_roster 抢走并 flatten；这里先按
    # 「全表命中简历标签 ≥3 且含简历标记」识别为 resume_each（每人一份，
    # 默认整表克隆），优先于人员/业绩一览表。
    if len(table.columns) >= 2:
        resume_hits, resume_cols = _match_resume_all(table)
        if len(resume_hits) >= 3 and _has_resume_markers(table):
            item["role"] = "resume_each"
            item["columns"] = resume_cols
            item["mode"] = "per_person"
            item["confidence"] = "高" if len(resume_hits) >= 5 else "低"
            return item

    # 规则 4：命中数判定人员表 / 业绩表。
    # 共享键归属裁定（T5）："序号"两族共有且匹配时 person 族优先锁定，
    # 纯业绩表会因此丢 seq。表角色判定完成后，把败方仅命中 seq 的共享键
    # 列补给胜方 columns。
    if len(person_map) >= 2 and len(person_map) >= len(perf_map):
        if "seq" not in person_map and set(perf_map) == {"seq"}:
            person_map = {**person_map, "seq": perf_map["seq"]}
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
        if "seq" not in perf_map and set(person_map) == {"seq"}:
            perf_map = {**perf_map, "seq": person_map["seq"]}
        item["role"] = "perf_list"
        item["columns"] = perf_map
        item["confidence"] = "高" if len(perf_map) >= 3 else "低"
        item["perf_scope"] = "lead" if "负责人" in heading else "all"
        return item

    # 规则 4.6/5：键值简历样表（2~5 列；V1.2 7.2 起大网格 ≥10 列同样识别，
    # 4~9 列中小表分类不变）。含「一人一表」标记（拟在本项目任职/主要工作
    # 经历/执业资格证书名称 任一）→ resume_each；否则 ≤3 列或大网格 →
    # lead_resume（旧行为）。
    ncols = len(table.columns)
    if (2 <= ncols <= 5) or ncols >= 10:
        hits, columns = _match_resume(table)
        if len(hits) >= 3:
            col0_text = "".join(
                _norm(p[0][1]) for p in
                (_dedup_col_texts(r) for r in table.rows) if p)
            if any(m in col0_text for m in RESUME_EACH_MARKERS):
                item["role"] = "resume_each"
                item["columns"] = columns
                # 一人一表默认整表克隆（V1.2 7.4：选 N 人 → N 张结构原样表；
                # 用户仍可在确认绑定时改回 ""）
                item["mode"] = "per_person"
                item["confidence"] = "高" if len(hits) >= 5 else "低"
                return item
            if ncols <= 3 or ncols >= 10:
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
