# Task 4: 拟派岗位列映射与跨行表头识别补强

**Files:**
- Modify: `backend/app/core/bid_table_classifier.py`（role 关键词、header_rows 补强）
- Modify: `backend/app/core/bid_draft_exporter.py`（确认 role 列写入，无需大改）
- Test: `backend/tests/test_bid_classifier.py`（追加）；`backend/tests/test_api_bid_draft.py`（header_rows 边界）

**Interfaces:**
- Produces: `PERSON_COL_KEYWORDS["role"]` 含 `"本项目任职"`, `"本项目职务"`；`classify_tables` 对人员表 role 列命中即写入 `columns`（列下标）。
- Consumes: Task 1-3 无直接依赖。

## 背景（实测）
人员汇总表「本项目任职/岗位/职务」列未映射拟派岗位（role），导出后该列空白。`role` 数据端已有（`person_semantics` 的 `"role"`，来自已保存勾选 role）。现有 role 关键词为 `("拟派岗位","拟任职务","本项目岗位")`，未含「本项目任职」。

## 步骤

- [ ] **Step 1: 写失败测试**

```python
def test_role_column_keywords_include_bendan():
    from app.core.bid_table_classifier import PERSON_COL_KEYWORDS
    assert "本项目任职" in PERSON_COL_KEYWORDS["role"]
    assert "本项目职务" in PERSON_COL_KEYWORDS["role"]


def test_person_roster_maps_role_column():
    from app.core.bid_table_classifier import classify_tables
    from docx import Document
    doc = Document(); t = doc.add_table(2, 3)
    for j, h in enumerate(["姓名", "学历", "本项目任职"]):
        t.rows[0].cells[j].text = h
    for j, v in enumerate(["张三", "硕士", "项目经理"]):
        t.rows[1].cells[j].text = v
    item = next(s for s in classify_tables(doc) if s["role"] == "person_roster")
    assert "role" in item["columns"]


def test_export_role_column_filled():
    # 通过 fill_draft：人员表 columns={"2":"role"}，person.sem["role"]="项目经理"
    # 断言产物该单元格 = "项目经理"（程序化构造 docx）
    ...
```

- [ ] **Step 2: 跑测试确认失败** → `python -m pytest tests/test_bid_classifier.py -q -k "role or bendan"`

- [ ] **Step 3: 实现**
  - `PERSON_COL_KEYWORDS["role"] = ("拟派岗位", "拟任职务", "本项目岗位", "本项目任职", "本项目职务")`。
  - 分类器逐列匹配已保证"长关键词优先、每语义一列"——`本项目岗位/任职/职务` 命中 role，不会与 `label`（人员安排/岗位/职务）混淆（label 不含"本项目/拟"），无需改逻辑。若发现 `职务` 单词在 `本项目任职` 之前命中 label，需调整匹配顺序为关键词长度降序（确认现有实现已如此）。
  - header_rows 补强（7.1）：在 `_classify_table` 现有两处 header_rows=2 之外，追加规则——第 0 行整行无数据语义（无数字/金额/纯姓名等）**且** 第 1 行命中表头关键词签名 → header_rows=2；结果写回建议项。
  - 确认 `test_api_bid_draft.py` 已有 header_rows 1..4 校验用例；若缺，补 `header_rows=3` 接受、`0`/`5` 返回 422。

- [ ] **Step 4: 跑测试** → `python -m pytest tests/test_bid_classifier.py tests/test_bid_draft_export.py tests/test_api_bid_draft.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/bid_table_classifier.py backend/tests/test_bid_classifier.py backend/tests/test_api_bid_draft.py
git commit -m "商务标：拟派岗位列映射与跨行表头识别补强"
```

## 全局约束
- 后端工作目录 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\backend`，跑 `python -m pytest`。
- role 列命中后数据端必须能取到 `person_semantics` 的 `"role"` 值（已存在），导出该列不得空白。
- 分类器改动不得使既有 14 个 classifier 测试回归；不得误把普通「职务」列当 role 抢走 label。
- 英文标识符、中文文案；真实数据只读，测试程序化构造。
- 独立 commit，message 前缀 `商务标：`。
