# Task 5: 简历表「一人一表」整表克隆（核心）

**Files:**
- Modify: `backend/app/core/bid_table_classifier.py`（新增角色 `resume_each`，与 `lead_resume` 区分）
- Modify: `backend/app/core/bid_draft_exporter.py`（克隆 + 逐人填充 + 报告）
- Modify: `backend/app/services/bid_service.py`（每人 `perfs_text`）
- Modify: `backend/app/services/bid_draft_service.py`（`_BINDING_KEYS` 增 `mode`）
- Modify: `backend/app/routers/bid_draft.py`（`TableBindingIn.mode` 字段+校验）
- Modify: `backend/app/core/bid_verify.py`（`table_insertions` 登记）
- Test: `backend/tests/test_bid_resume_clone.py`（新建）

**Interfaces:**
- Produces:
  - 分类器 `ROLES` 增 `"resume_each"`；键值样表（命中 `RESUME_LABELS` ≥3 不同标签 **且** 含"拟在本项目任职"/"主要工作经历"/"执业资格证书名称" 任一）→ `resume_each`。
  - `TableBindingIn.mode: str = ""`（`"per_person"` 时整表克隆；其他/空=现行为）；`_BINDING_KEYS` 含 `"mode"`。
  - `assemble_bid_draft_data` 每个 person 增 `"perfs_text": str`（该人名下业绩 `"项目名称（年份）"` 换行连接；无→""），`lead_perfs_text` 保留。
  - `_fill_resume_table(table, label_to_sem, sem, perfs_text)`（perfs 文本随人传入）。
  - `clone_table_after(table) -> Table`（XML 级 `deepcopy(table._tbl)`，`addnext`，前后保留空段落分隔）。
  - `verify_draft_fill(..., table_insertions: dict[int,int] = None)`。

## 背景（V1.2 7.4，实测）
招标文件「主要人员简历表」是键值结构样表（姓名/年龄/执业资格证书 → 职称/学历/拟在本项目任职 → 工作年限 → 毕业学校 → 主要工作经历 → 明细行）。一期导出将其改写为"一人一行"扁平列表，结构被破坏。要求：选 N 人 → N 张结构原样的表；无内容留空，绝不增删行列。

## 步骤

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_bid_resume_clone.py
from docx import Document
from app.core.bid_draft_exporter import fill_draft


def _sample_resume_table(doc):
    t = doc.add_table(2, 2)
    t.rows[0].cells[0].text = "姓名"; t.rows[0].cells[1].text = ""
    t.rows[1].cells[0].text = "主要工作经历"; t.rows[1].cells[1].text = ""
    return t


def test_per_person_clone_count_and_structure(tmp_path):
    src = tmp_path / "draft.docx"; dst = tmp_path / "out.docx"
    doc = Document(); _sample_resume_table(doc); doc.save(src)
    persons = [
        {"name": "张三", "is_lead": True, "role": "项目经理",
         "sem": {"name": "张三"}, "perfs_text": "甲项目（2024）", "fields": {}},
        {"name": "李四", "is_lead": False, "role": "造价员",
         "sem": {"name": "李四"}, "perfs_text": "乙项目（2023）", "fields": {}},
    ]
    data = {"persons": persons, "contracts": [], "lead_perfs_text": "甲项目（2024）"}
    bindings = {"tables": [{"table_index": 0, "role": "resume_each",
                            "columns": {"姓名": "name", "主要工作经历": "lead_perfs"},
                            "mode": "per_person", "confirmed": True}],
                "swap_toc": False}
    report = fill_draft(str(src), str(dst), bindings, data,
                        project_no="", project_name="", doc_date="")
    out = Document(str(dst))
    assert len(out.tables) == 2                       # 样表 + 1 克隆
    assert out.tables[0].rows[0].cells[1].text == "张三"
    assert out.tables[1].rows[0].cells[1].text == "李四"
    assert report["verify"]["ok"] is True             # 克隆已登记，不误报
    assert report["filled"][0]["cloned"] == 2


def test_clone_preserves_row_col_count(tmp_path):
    # 样表行列数 == 每份克隆行列数（deepcopy 保留结构）
    ...
```

- [ ] **Step 2: 跑测试确认失败** → `python -m pytest tests/test_bid_resume_clone.py -q`

- [ ] **Step 3: 实现**

**分类器**：新增 `resume_each` 判定，排在 `lead_resume` 之前。触发条件（键值样表特征）：表格 2~5 列、`RESUME_LABELS` 命中 ≥3 个不同标签、且含「拟在本项目任职」/「主要工作经历」/「执业资格证书名称」任一。`lead_resume` 保留给不满足 `resume_each` 的旧样表（向后兼容）。`ROLES` 元组加 `"resume_each"`。

**bid_service**：抽出 `_perf_lines_for(name, contracts)`（复用现有 `lead_perfs_text` 逻辑），对每个 person 计算 `p["perfs_text"] = "\n".join(lines)`；`lead_perfs_text` 改为 lead 的 `perfs_text`（保持旧键兼容）。

**bid_draft_exporter**：
```python
def _clone_table_after(table):
    tbl = table._tbl
    new = deepcopy(tbl)
    sep = tbl.makeelement(qn("w:p"), {})
    tbl.addnext(sep); tbl.addnext(new)
    from docx.table import Table
    return Table(new, table._parent)
```
`fill_draft` 新增 `resume_each` 分支：
- `picked = _scope_persons(persons, binding.get("person_scope") or "all")`。
- 第 1 份填原样表，其余 `len(picked)-1` 份 `clone_table_after` 后逐份 `_fill_resume_table`；每人 `perfs_text = p.get("perfs_text") or (data.get("lead_perfs_text") if p.get("is_lead") else "")`。
- 记录 `table_insertions[orig_idx] = len(picked)-1`（传给 verify）。
- 仅当 `binding.get("mode") == "per_person"` 时克隆；否则等同 `lead_resume`（单份单填 lead）保持旧行为。
- `report["filled"].append({"table_index": idx, "role": "resume_each", "rows": total, "cloned": len(picked)})`。
- `lead_resume` 分支改调 `_fill_resume_table(..., perfs_text=lead.get("perfs_text") or data.get("lead_perfs_text") or "")`。
- `bound_indices` 的 role 元组加 `"resume_each"`。
- `verify_draft_fill(..., table_insertions=table_insertions)`。

**bid_verify.verify_draft_fill** 增 `table_insertions: dict[int,int] = None`：
```python
insertions = dict(table_insertions or {})
total_added = sum(int(v) for v in insertions.values())
if len(o_tables) != len(d_tables) + total_added:
    issues.append(...)
draft_to_out, shift = {}, 0
for i in range(len(d_tables)):
    draft_to_out[i] = i + shift
    shift += int(insertions.get(i, 0))
clone_idx = set()
for i, n in insertions.items():
    base = draft_to_out[i]
    clone_idx.update(range(base + 1, base + 1 + int(n)))
```
比对循环 `o_tab = o_tables[draft_to_out[i]]`（`i in bound` 跳过）；`clone_idx` 无底稿对应，仅计入数量等式。

**bid_draft_service / routers/bid_draft**：`_BINDING_KEYS` 加 `"mode"`；`TableBindingIn` 加 `mode: str = ""`；校验 mode ∈ {"", "per_person"}（非法 422）；preview 回显 mode。

- [ ] **Step 4: 跑测试**

Run: `python -m pytest tests/test_bid_resume_clone.py tests/test_bid_draft_export.py tests/test_bid_verify.py tests/test_bid_draft_service.py tests/test_api_bid_draft.py tests/test_bid_classifier.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/bid_table_classifier.py backend/app/core/bid_draft_exporter.py backend/app/services/bid_service.py backend/app/services/bid_draft_service.py backend/app/routers/bid_draft.py backend/app/core/bid_verify.py backend/tests/test_bid_resume_clone.py backend/tests/test_bid_draft_service.py backend/tests/test_api_bid_draft.py
git commit -m "商务标：简历表一人一表整表克隆（含校验登记）"
```

## 全局约束
- 后端工作目录 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\backend`，跑 `python -m pytest`。
- 克隆必须完整保留行列数、合并单元格、行高与样式（deepcopy table XML，非重建）。
- 克隆表必须登记进 verify（`table_insertions`），否则表数量校验误报；填充端与校验端共用同一登记。
- 无 `mode=per_person` 时保持旧行为（单份 lead 填充），既有测试不回归。
- 英文标识符、中文文案；真实数据只读，测试程序化构造。
- 独立 commit，message 前缀 `商务标：`。
