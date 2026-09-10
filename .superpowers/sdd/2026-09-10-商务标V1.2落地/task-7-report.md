# Task 7 报告：简历大网格矩阵填充（P3）

## 实现内容

1. **`app/core/bid_draft_exporter.py`**
   - `expand_table_matrix(table)`：按 `w:tr`/`w:tc` 展开逻辑网格，
     `gridSpan@val` 跨列各格指向同一 origin `w:tc`；`vMerge`（`restart` 起区 /
     无 val 或 `continue` 续区）按列回填，续行格映射到 restart origin；
     返回 `matrix[r][c] = origin w:tc`（元素引用，`is` 可判等）。
   - `_fill_resume_grid_mesh(table, label_to_sem, sem, perfs_text)`：遍历矩阵，
     每个 origin 只作 label 处理一次（规范化 `strip().rstrip("：:")` 命中
     label_to_sem）→ 同行右侧首个不同 origin 格，无右邻则下方行同列首个
     不同 origin 格；`lead_perfs` 写 `perfs_text`；返回写入格数。
   - `_is_grid_resume(table)`：列数 ≥10 或 vMerge/gridSpan 合计 ≥3 处。
   - `_fill_resume_auto(...)`：分流 网格 → mesh / 中小表 → 原
     `_fill_resume_table`，返回 `(写入格数, 是否网格)`。
   - `fill_draft` 的 `lead_resume`/`resume_each`（含 per_person 每份克隆）
     改走 `_fill_resume_auto`；网格模式时 `filled` 条目记 `"mode": "grid"`。
2. **`app/core/bid_table_classifier.py`**：简历规则合并改写——2~5 列
   （含标记 → resume_each / ≤3 列 → lead_resume）行为不变；新增
   ≥10 列大网格同样识别（含标记 → resume_each，无标记 → lead_resume）；
   4~9 列分类不变。模块 docstring 规则 5 同步更新。
3. **测试**（`tests/test_bid_draft_export.py` 追加 6 个）：矩阵恒等、
   右写+下写、纯下方写（无右邻）、gridSpan 跨列同 origin + 右写、
   vMerge 续行映射 origin + 续行不写、fill_draft 端到端大网格
   （10 列不重建、两标签格写值、mode="grid"、verify.ok）。

## TDD 证据

- **RED**：`python -m pytest tests/test_bid_draft_export.py -q -k grid` →
  收集期 `ImportError: cannot import name 'expand_table_matrix'`（接口未实现）。
- **GREEN**：`python -m pytest tests/test_bid_draft_export.py
  tests/test_bid_classifier.py tests/test_bid_resume_clone.py -q` →
  `50 passed in 5.16s`。
- **全量回归**：`python -m pytest -q` → `330 passed in 60.14s`
  （324 + 新增 6；既有 lead_resume/resume_each 用例全绿）。

## 自审查

- 不重建表：mesh 只 `_set_cell_text` 写目标格，合并结构/行列数不动
  （端到端用例断言行列数不变）；vMerge 续行不写（测）。
- 无回归：中小简历表仍走 `_fill_resume_table`（`_is_grid_resume` 对 2~3 列
  无合并表为 False）；既有 `filled` 条目仅在网格模式多一个 `mode` 键，
  旧断言（精确等值的 filled 条目）未涉及简历条目，全量绿实证。
- 分类器放宽仅限 ≥10 列（此前这类表必为 ignore），不改变 2~9 列判定。
- YAGNI：未实现并查集（按列回填字典已等价且更简单）；brief 类型标注
  `list[list[tuple[int,int]]]` 与其文字描述（origin 引用）矛盾，按描述
  实现为元素引用。

## 关注点

- 「合并格密度高」量化为 vMerge+gridSpan 合计 ≥3 处（brief 未给阈值）；
  真实大网格简历表合并远多于此，中小键值表一般 0 处，区分度充足。
- `_fill_resume_grid_mesh` 的「下方」检索限同列；跨列标签+下方值的
  异型布局（标签占满整行的横向合并行）由"右侧优先"覆盖不到时会写
  下方同列——与 brief 一致。

## 提交

- `9ce8d35` 商务标：简历大网格矩阵填充
