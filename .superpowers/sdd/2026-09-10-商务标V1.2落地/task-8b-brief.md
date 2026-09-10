# Task 8b: 导出报告纳入占位符清单（后端）

**Files:**
- Modify: `backend/app/core/bid_draft_exporter.py`（`fill_draft` 报告增 `placeholders` 键）
- Test: `backend/tests/test_bid_draft_export.py` 或 `test_bid_placeholders.py`（追加）

**背景**：V1.2 4.3 要求"填充后在报告中输出 placeholders filled / skipped，未识别的疑似占位列入报告提示，不静默"（验收标准 7）。Task 1 已实现 `scan_placeholders(doc, params, synonyms=None) -> {"matched":[{label,value,count,kind}], "suspicious":[{text}]}`，但 `fill_draft` 返回的 `report` 尚无 `placeholders` 键，前端 Task 8 报告对话框无数据可渲染。

**Interfaces（Produces）：**
- `fill_draft` 返回的 `report` 增 `"placeholders": {"filled": [{"label","value","count","kind"}], "suspicious": [{"text"}]}`。
- 计算时机：加载底稿后、任何替换之前，对底稿调用 `scan_placeholders(doc, params, synonyms=synonyms)`；params 由 `project_no/project_name/doc_date/tenderer/bidder_name/section_name/section_no` 组成（键名与 `build_placeholder_rules` 一致，空串照传）。
- 无命中时仍返回空列表（键恒存在）。
- `filled` = `matched`（识别到并将填入的值）；`suspicious` = 未识别成串下划线。

## 步骤
- [ ] Step 1: 写失败测试
  - 底稿含 `招标人：____` 与一行 `______________________________`；`fill_draft(..., tenderer="某中心")` 后 `report["placeholders"]["filled"]` 含 label `招标人`/value `某中心`，`suspicious` 非空；`report["verify"]["ok"] is True`。
  - 无占位符底稿 → 两键均为空列表（键存在）。
- [ ] Step 2: 跑测试确认失败 → `python -m pytest tests/test_bid_draft_export.py -q -k placeholder`
- [ ] Step 3: 实现（仅调用 `scan_placeholders`，不复制规则；不改填充/校验逻辑）。
- [ ] Step 4: 跑聚焦，再全量 `python -m pytest -q`（基线 336 passed）。
- [ ] Step 5: Commit `商务标：导出报告纳入占位符清单`

## 全局约束
- 后端工作目录 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\backend`，跑 `python -m pytest`。
- 报告新增键不得影响既有报告断言；规则只经 `scan_placeholders`。
- 英文标识符、中文文案；真实数据只读，测试程序化构造。
- 独立 commit，message 前缀 `商务标：`。
