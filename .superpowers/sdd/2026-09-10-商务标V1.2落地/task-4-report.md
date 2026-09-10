# Task 4 报告：拟派岗位列映射与跨行表头识别补强

## 实现内容

1. **`app/core/bid_table_classifier.py`**
   - `PERSON_COL_KEYWORDS["role"]` 追加 `"本项目任职"`、`"本项目职务"`
     （现为 `("拟派岗位","拟任职务","本项目岗位","本项目任职","本项目职务")`）。
     现有 `_match_columns` 已是长关键词优先 + 每列一语义 + 每语义一列：
     「本项目职务」中的「职务」（label，2 字）竞争不过「本项目职务」（role，5 字），
     role 抢列成功、label 不截胡——逻辑无需改，仅补关键词。
   - header_rows 第三识别规则（7.1）：新增 `_row_has_data_semantics(pairs)`
     （任一单元格含数字即视为有数据语义）；在既有两条 header_rows=2 规则之后
     追加 elif——row0 命中表头关键词但整行无数据语义 且 row1 也命中表头
     关键词签名（≥2）→ `header_rows=2`（双层表头各行皆含关键词的场景，
     此前因 row0 命中足够且 row1 文本不重复而漏判为 1）。
2. **`bid_draft_exporter.py`**：未改（确认 `_fill_table_semantic` 已按
   `col_to_sem` 写入 `sem["role"]`，端到端测试实证——见下）。
3. **测试**
   - `tests/test_bid_classifier.py` 追加 5 个：
     `test_role_column_keywords_include_bendan`（brief 原文）、
     `test_person_roster_maps_role_column`（「本项目任职」列入 columns；
     brief 片段把 Document 直接传给 classify_tables，但该函数收路径，
     按文件内既有 `_save(tmp_path)` 模式适配）、
     `test_role_beats_label_on_bendan_zhiwu`（「本项目职务」role 抢列、
     label 不得截胡）、
     `test_header_rows_two_when_row0_no_data_and_row1_header`（第三规则）、
     `test_export_role_column_filled`（fill_draft 端到端：role 列写入
     「项目经理」且 verify.ok）。
   - `tests/test_api_bid_draft.py` 追加 `test_put_bindings_header_rows_three_accepted`
     （既有用例已覆盖 0/5→422 与 2 回显，补 header_rows=3 接受 + 回显；
     API 合法域 1..4 未动）。

## TDD 证据

- **RED**：`python -m pytest tests/test_bid_classifier.py -q -k "role or bendan"`
  → `3 failed`（关键词缺失 / columns 无 role / label 截胡 col2）；
  `test_header_rows_two_when_row0_no_data_and_row1_header` → `assert 1 == 2`。
  （`test_export_role_column_filled` 一次通过——填充端本就通用，缺口只在分类器。）
- **GREEN**：`python -m pytest tests/test_bid_classifier.py
  tests/test_bid_draft_export.py tests/test_api_bid_draft.py -q` →
  `58 passed in 12.62s`。
- **全量回归**：`python -m pytest -q` → `308 passed in 56.17s`（302 + 新增 6，
  既有 14+ 个 classifier 用例全绿）。

## 自审查

- 回归风险排查：第三规则只会在「row0 命中≥2 且无数字 且 row1 也命中≥2 个
  表头关键词」时把 header_rows 从 1 改 2；逐个人工核对既有 classifier 用例
  （数据行关键词命中均为 0，或被 quote/image_slot/concat/shared 等前置分支
  拦截），全量测试实证无回归。
- 既有 `test_header_rows_two_when_subheader_repeats_row0`（真实 17×10 底稿
  回归）表头恰含「本项目任职」列——本任务后该列也进 columns（role），
  正属 7.6 要修的缺口；该用例断言不受影响。
- YAGNI：未改 `_match_columns` 匹配逻辑、未动 API 校验区间、未改导出端。
- 编辑事故：追加测试时误删既有测试 def 行尾换行，已立即恢复并经全量测试确认。

## 关注点

- 第三规则的「无数据语义」信号仅为「不含数字」（按 brief 的"无数字/金额/纯
  姓名等"取最客观信号）；若某表 row0 表头本身含数字（如「2026 年人员表」）
  且 row1 是副表头，仍靠拼接兜底/共享副表头两条规则覆盖。
- `test_export_role_column_filled` 放在 test_bid_classifier.py（commit 清单
  只含该测试文件）；语义上属导出端，但 assertion 目标即分类器 columns 契约。

## 提交

- `fbf6754` 商务标：拟派岗位列映射与跨行表头识别补强
