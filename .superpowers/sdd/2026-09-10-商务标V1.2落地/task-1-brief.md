# Task 1: 占位符规则核心（含文本框遍历与校验对称）

**Files:**
- Modify: `backend/app/core/bid_template_exporter.py:228-357`
- Modify: `backend/app/core/bid_verify.py:29-125`
- Modify: `backend/app/settings_store.py`（新增默认同义词常量+存取，设置 API 在 Task 9 接）
- Test: `backend/tests/test_bid_placeholders.py`（新建）

**Interfaces:**
- Produces:
  - `DEFAULT_PLACEHOLDER_SYNONYMS: dict[str,str]`
  - `PLACEHOLDER_LABEL_KEYS: dict[str,str]`（规范标签→参数键）
  - `BRACKET_LABEL_KEYS: dict[str,str]`（括号标签→参数键）
  - `_iter_textbox_paragraphs(doc) -> Iterator[Paragraph]`（含嵌套文本框内段落，不重复）
  - `_iter_all_paragraphs(doc)`（原体+表格+文本框）
  - `build_placeholder_rules(doc, *, project_no="", project_name="", doc_date="", tenderer="", bidder_name="", section_name="", section_no="", synonyms=None) -> list[dict]`
    每项：`{"kind","label","key","value","pattern","repl"}`
  - `compute_text_subs(doc, project_no="", project_name="", doc_date="", tenderer="", bidder_name="", section_name="", section_no="", synonyms=None) -> list[tuple[Pattern, repl]]`（= rules 的 `(pattern,repl)`）
  - `scan_placeholders(doc, params: dict, synonyms=None) -> {"matched":[{"label","value","count","kind"}], "suspicious":[{"text"}]}`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_bid_placeholders.py
import re
from docx import Document
from docx.shared import Cm

from app.core.bid_template_exporter import (
    DEFAULT_PLACEHOLDER_SYNONYMS, _iter_all_paragraphs,
    _iter_textbox_paragraphs, build_placeholder_rules, scan_placeholders,
)


def _doc_with(paras):
    doc = Document()
    for p in paras:
        doc.add_paragraph(p)
    return doc


def test_label_blank_fills_expanded_labels():
    doc = _doc_with(["项目名称：____", "采购人：____", "标段名称：____",
                     "标段编号：", "日期：____年__月__日"])
    rules = build_placeholder_rules(
        doc, project_name="里下河项目", tenderer="某中心",
        section_name="一标段", section_no="A1", doc_date="2026-09-10")
    full = "\n".join(p.text for p in _iter_all_paragraphs(doc))
    for r in rules:
        full = r["pattern"].sub(r["repl"], full)
    assert "项目名称：里下河项目" in full
    assert "采购人：某中心" in full          # 同义词 采购人→招标人
    assert "标段名称：一标段" in full
    assert "标段编号：A1" in full
    assert "日期：2026年9月10日" in full


def test_bracket_half_and_full_width_filled():
    doc = _doc_with(["(项目名称) (标段名称)", "（招标人名称）（投标人名称）"])
    rules = build_placeholder_rules(
        doc, project_name="P", tenderer="T", bidder_name="B",
        section_name="S")
    full = "\n".join(p.text for p in _iter_all_paragraphs(doc))
    for r in rules:
        full = r["pattern"].sub(r["repl"], full)
    assert "P (S)" in full
    assert "T" in full and "B" in full
    assert "（" not in full and "(项目名称)" not in full


def test_textbox_paragraphs_are_traversed_and_no_dup():
    doc = Document()
    p = doc.add_paragraph()
    run = p.add_run()
    # 构造一个含 w:txbxContent 的极简 drawing
    xml = (
        '<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData '
        'uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        '<wps:wsp xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        '<wps:txbx><w:txbxContent><w:p><w:r><w:t>招标人：____</w:t></w:r></w:p>'
        '</w:txbxContent></wps:txbx></wps:wsp></a:graphicData></a:graphic></wp:inline>'
        '</w:drawing></w:r></w:p>')
    from lxml import etree
    p._p.addnext(etree.fromstring(xml))
    texts = [t.text for t in _iter_textbox_paragraphs(doc)]
    assert texts.count("招标人：____") == 1


def test_scan_placeholders_reports_match_and_suspicious():
    doc = _doc_with(["招标人：____", "______________________________"])
    res = scan_placeholders(doc, {"tenderer": "某中心"})
    assert any(m["label"] == "招标人" and m["value"] == "某中心"
               for m in res["matched"])
    assert res["suspicious"], "孤立下划线应列入可疑清单"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_bid_placeholders.py -q`
Expected: FAIL（`build_placeholder_rules`/`scan_placeholders`/`_iter_textbox_paragraphs` 未定义）

- [ ] **Step 3: 实现规则核心**

在 `bid_template_exporter.py` 追加（保留旧 `_TENDERER_LABEL_RE`/`_BIDDER_LABEL_RE` 供旧路径），实现要点：

```python
DEFAULT_PLACEHOLDER_SYNONYMS = {
    "工程项目名称": "项目名称", "工程名称": "项目名称",
    "采购人": "招标人", "供应商名称": "投标人名称",
}
PLACEHOLDER_LABEL_KEYS = {
    "项目名称": "project_name", "招标人": "tenderer",
    "投标人名称": "bidder_name", "项目编号": "project_no",
    "招标编号": "project_no", "标段名称": "section_name",
    "标段编号": "section_no", "日期": "doc_date",
}
BRACKET_LABEL_KEYS = {
    "项目名称": "project_name", "工程名称": "project_name",
    "工程项目名称": "project_name", "招标人名称": "tenderer",
    "招标人": "tenderer", "采购人": "tenderer",
    "投标人名称": "bidder_name", "供应商名称": "bidder_name",
    "标段名称": "section_name", "标段编号": "section_no",
    "标段": "section_name", "日期": "doc_date",
}
_SECTION_COMBO_RE = re.compile(
    r"[（(]\s*(?:项目名称|工程名称|工程项目名称)\s*[）)]\s*"
    r"[（(]\s*标段(?:名称)?\s*[）)]")
_UNRECOGNIZED_UNDERSCORE_RE = re.compile(r"_{4,}|＿{4,}")


def _effective_label_keys(synonyms):
    keys = dict(PLACEHOLDER_LABEL_KEYS)
    for alias, canonical in (synonyms or DEFAULT_PLACEHOLDER_SYNONYMS).items():
        key = PLACEHOLDER_LABEL_KEYS.get(canonical)
        if key and alias not in keys:
            keys[alias] = key
    return keys


def _date_text(doc_date):
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", (doc_date or "").strip())
    return f"{int(m.group(1))}年{int(m.group(2))}月{int(m.group(3))}日" if m else ""
```

`build_placeholder_rules` 生成（顺序：stale → 组合 → 标签长度降序 → 括号长度降序 → 日期）：

- stale：沿用 `_discover_stale_values`（`kind="stale_no"/"stale_name"`）。
- 组合：当 `project_name and section_name` 且底稿命中 `_SECTION_COMBO_RE` → repl = `f"{project_name}（{section_name}）"`。
- 标签：对 `_effective_label_keys` 每个 label 且 value 非空 →
  `re.compile(rf"({re.escape(label)}\s*[：:])(?=[\s_　＿]|$)[\s_　＿]*")`，repl=lambda m, l=label, v=value: m.group(1)+v。
  标签按长度降序（避免"项目名称"截胡"工程项目名称"）。
- 括号：对 `BRACKET_LABEL_KEYS` 且 value 非空 →
  `re.compile(rf"[（(【\[]\s*{re.escape(label)}\s*[）)】\]]")`，repl=value。按长度降序。
- 日期：`_DOC_DATE_RE`（带数字）与新增 `_DOC_DATE_BLANK_RE = re.compile(r"(日\s*期\s*[：:]?\s*)[_＿\s]*年[_＿\s]*月[_＿\s]*日")`，
  repl=lambda m: m.group(1)+date_text。仅当 date_text 非空。

`compute_text_subs` 改为 `[(r["pattern"], r["repl"]) for r in build_placeholder_rules(...)]`，参数签名加 `section_name/section_no/synonyms` 默认空。

`_iter_textbox_paragraphs`：

```python
def _iter_textbox_paragraphs(doc):
    for txbx in doc.element.body.iter(qn("w:txbxContent")):
        for child in txbx.iterchildren():
            if child.tag == qn("w:p"):
                yield Paragraph(child, doc)
            elif child.tag == qn("w:tbl"):
                for row in Table(child, doc).rows:
                    for cell in row.cells:
                        yield from _iter_cell_paragraphs(cell)
```

`_iter_all_paragraphs` = 现有三部分 + `_iter_textbox_paragraphs(doc)`。
`scan_placeholders` 遍历 `build_placeholder_rules` 的每条 rule，在 `_iter_all_paragraphs`（跳过 toc）上 `pattern.findall/subn` 计数；`count>0` 记入 `matched`；未被任何规则命中的 `_UNRECOGNIZED_UNDERSCORE_RE` 段落文本记入 `suspicious`。

`settings_store.py` 追加：

```python
from app.core.bid_template_exporter import DEFAULT_PLACEHOLDER_SYNONYMS

def get_placeholder_synonyms() -> dict:
    raw = load_settings().get("placeholder_synonyms") or {}
    base = dict(DEFAULT_PLACEHOLDER_SYNONYMS)
    for alias, canonical in raw.items():
        alias, canonical = str(alias).strip(), str(canonical).strip()
        if alias and canonical:
            base[alias] = canonical
    return base

def save_placeholder_synonyms(m: dict) -> dict:
    clean = {str(k).strip(): str(v).strip()
             for k, v in (m or {}).items() if str(k).strip() and str(v).strip()}
    s = load_settings(); s["placeholder_synonyms"] = clean; save_settings(s)
    return clean
```

- [ ] **Step 4: 校验端对称**

在 `bid_verify.py` 增加：

```python
from app.core.bid_template_exporter import _iter_textbox_paragraphs

def _textbox_texts(doc, subs=None):
    out = []
    for p in _iter_textbox_paragraphs(doc):
        t = _para_text(p)
        if subs and not _is_toc_paragraph(p):
            t = _apply_subs(t, subs)
        out.append(t)
    return out
```

`verify_draft_fill` 的 `compute_text_subs` 调用补 `section_name=params.get("section_name") or ""`、`section_no=...`、`synonyms=params.get("synonyms")`；末尾追加：若 `_textbox_texts(draft, subs) != _textbox_texts(out)` → issue `"文本框内容被改动"`（数量不一报数量，逐个不等报下标）。

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/test_bid_placeholders.py tests/test_bid_verify.py tests/test_bid_template.py -q`
Expected: PASS（旧 verify 测试不回归）

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/bid_template_exporter.py backend/app/core/bid_verify.py backend/app/settings_store.py backend/tests/test_bid_placeholders.py
git commit -m "商务标：通用占位符规则核心（标签/括号/日期/文本框+校验对称）"
```

## 全局约束（必须遵守）

- 后端工作目录 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\backend`，跑 `python -m pytest`。
- 填充端与校验端**必须共用** `build_placeholder_rules`/`compute_text_subs` 与段迭代器；新规则必须让 verify 同时豁免。
- 英文标识符、中文文案；不改旧模板导出路径既有行为；真实数据只读，测试程序化构造。
- 每个任务独立 commit，message 前缀 `商务标：`。
