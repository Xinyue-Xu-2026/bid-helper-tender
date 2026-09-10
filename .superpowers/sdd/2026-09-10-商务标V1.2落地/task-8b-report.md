# Task 8b 报告：导出报告纳入占位符清单（后端）

## 实现内容

1. **`app/core/bid_draft_exporter.py`**：`fill_draft` 的 `report` 增
   `"placeholders": {"filled": [...], "suspicious": [...]}`（键恒存在，
   无命中为空列表）。计算时机：加载底稿后、`_replace_stale_text` 之前，
   调 `scan_placeholders(doc, params, synonyms=synonyms)`——params 为
   `project_no/project_name/doc_date/tenderer/bidder_name/section_name/
   section_no`（空串照传，键名与 `build_placeholder_rules` 一致），
   synonyms 用 `fill_draft` 收到的同一份（与填充/校验同源）。
   `filled = scan["matched"]`，`suspicious = scan["suspicious"]`。
   规则零复制，填充/校验逻辑未动。
2. **测试**（`tests/test_bid_placeholders.py` 追加 2 个）：
   - `test_fill_draft_report_includes_placeholders`：底稿含 `招标人：____`
     + 孤立下划线行 → filled 含 招标人/某中心、suspicious 非空、
     verify.ok 为真。
   - `test_fill_draft_report_placeholders_empty_keys`：无占位符底稿 →
     两键空列表。
3. **既有断言同步**：`test_bid_draft_export.py` 的报告键精确集合断言
   `set(report) == {...}` 增加 `"placeholders"`（新增键必需同步，
   同 Task 3 的 images 键处理）。

## TDD 证据

- **RED**：`python -m pytest tests/test_bid_placeholders.py -q -k
  placeholder` → `2 failed`（`KeyError: 'placeholders'`）。
- **GREEN**：`python -m pytest tests/test_bid_placeholders.py
  tests/test_bid_draft_export.py -q` → `33 passed in 4.53s`。
- **全量回归**：`python -m pytest -q` → `338 passed in 62.60s`
  （336 基线 + 新增 2）。

## 自审查

- 规则唯一来源：fill_draft 仅调 `scan_placeholders`，未复制任何匹配逻辑；
  预览端点、导出报告、填充、校验四处同一套规则。
- 键恒存在（report 初始化即给默认空结构），前端可直接渲染。
- YAGNI：未加 skipped 占位语义（brief 未定义 skipped 清单内容，
  未识别项已由 suspicious 覆盖）。

## 关注点

- 扫描基于**替换前**底稿，`filled` 表示"识别到且将填入"——若某规则值
  为空（参数未传）则不产生 matched 项，自然体现"未填"。
- suspicious 目前只含成串下划线段落（`_UNRECOGNIZED_UNDERSCORE_RE`），
  其他形态的未识别占位（如裸括号词）不在其列——Task 1 既定语义。

## 提交

- `55e83e9` 商务标：导出报告纳入占位符清单
