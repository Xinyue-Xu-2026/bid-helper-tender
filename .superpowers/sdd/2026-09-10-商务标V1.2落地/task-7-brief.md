# Task 7: 简历大网格矩阵填充（P3）

**Files:**
- Modify: `backend/app/core/bid_draft_exporter.py`（新增 `expand_table_matrix` / `_fill_resume_grid_mesh`）
- Modify: `backend/app/core/bid_table_classifier.py`（大网格识别：列数≥10 或密集合并 → 仍 `lead_resume`/`resume_each`，导出走矩阵）
- Test: `backend/tests/test_bid_draft_export.py`（追加）

**Interfaces:**
- Produces:
  - `expand_table_matrix(table) -> list[list[tuple[int,int]]]`：把 `vMerge`/`gridSpan` 展开为逻辑网格，每格映射到其 origin `w:tc` 的引用（续行/跨列指向同一 origin `_tc`）。
  - `_fill_resume_grid_mesh(table, label_to_sem, sem, perfs_text) -> int`：对每个标签 origin 格，按矩阵坐标写右侧/下方首个不同 origin `_tc`；`lead_perfs` 写 `perfs_text`。

## 背景（V1.2 7.2）
对归类为简历表的大网格（列数≥10 或含密集合并单元格），不做整表重建，改为格子级填充：按 vMerge/gridSpan 展开为逻辑单元格矩阵，label→语义键匹配后按矩阵坐标写右侧/下方目标格，复用 `_fill_resume_table` 的匹配逻辑并扩展。

## 步骤

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_bid_draft_export.py 追加
from docx import Document
from docx.oxml.ns import qn
from app.core.bid_draft_exporter import expand_table_matrix, _fill_resume_grid_mesh


def _grid_table(doc):
    # 2x2 表：标签格在 (0,0)，值在 (0,1)；(1,0) 标签，值在 (1,1)
    t = doc.add_table(2, 2)
    t.rows[0].cells[0].text = "姓名"
    t.rows[1].cells[0].text = "主要工作经历"
    return t


def test_expand_table_matrix_identity_for_plain_grid():
    doc = Document(); t = _grid_table(doc)
    m = expand_table_matrix(t)
    assert len(m) == 2 and len(m[0]) == 2
    assert m[0][0] == m[0][0]  # origin 稳定


def test_grid_mesh_writes_right_and_below():
    doc = Document(); t = _grid_table(doc)
    written = _fill_resume_grid_mesh(
        t, {"姓名": "name", "主要工作经历": "lead_perfs"},
        {"name": "张三"}, "甲项目（2024）")
    assert t.rows[0].cells[1].text == "张三"
    assert t.rows[1].cells[1].text == "甲项目（2024）"
    assert written == 2


def test_grid_span_label_writes_right_origin():
    # 横向合并标签格 gridSpan=2 → 右侧首个不同 origin 目标格
    ...
```

- [ ] **Step 2: 跑测试确认失败** → `python -m pytest tests/test_bid_draft_export.py -q -k grid`

- [ ] **Step 3: 实现**
  - `expand_table_matrix`：按 `w:tr` → 展开每个 `w:tc`（`gridSpan@val` 列数，缺省 1）；`vMerge`（`val="restart"` 起区、无 val/continue 续区）用并查集/坐标回填把同列同区映射到 origin `_tc`；返回每行逻辑格 → origin `_tc` 引用矩阵。
  - `_fill_resume_grid_mesh`：遍历矩阵找 label 格（`cell.text` 规范化 `strip().rstrip("：:")`）命中 `label_to_sem` → 同行右邻列首个 origin≠自身的格 → 写；无右邻则下方行同列首个不同 origin → 写；语义键 `lead_perfs` 写 `perfs_text`。返回写入格数。
  - 导出分支：`lead_resume`/`resume_each` 且 `列数≥10 或 合并格密度高` → 调 `_fill_resume_grid_mesh`（否则沿用 `_fill_resume_table`）；结果记入报告 `filled` 且 `mode:"grid"`。克隆（`resume_each` per_person）每份克隆后同样按矩阵填充。
  - 分类器：确认大网格仍归 `resume_each`/`lead_resume`（列数放宽或合并密度判定），不改变既有中小表的分类。

- [ ] **Step 4: 跑测试** → `python -m pytest tests/test_bid_draft_export.py tests/test_bid_classifier.py tests/test_bid_resume_clone.py -q`；再全量 `python -m pytest -q`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/bid_draft_exporter.py backend/app/core/bid_table_classifier.py backend/tests/test_bid_draft_export.py
git commit -m "商务标：简历大网格矩阵填充"
```

## 全局约束
- 后端工作目录 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\backend`，跑 `python -m pytest`。
- 不做整表重建；网格在逻辑坐标上填充，保留原合并结构。
- 既有 `lead_resume`/`resume_each`（小/中表）走原 `_fill_resume_table`，不得回归；全量 324 passed 保持。
- 英文标识符、中文文案；真实数据只读，测试程序化构造。
- 独立 commit，message 前缀 `商务标：`。
