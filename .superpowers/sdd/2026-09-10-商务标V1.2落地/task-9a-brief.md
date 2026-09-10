# Task 9a: 导出端接入占位符同义词库（后端）

**Files:**
- Modify: `backend/app/core/bid_draft_exporter.py`（`fill_draft` 增 `synonyms` 入参并透传）
- Modify: `backend/app/core/bid_template_exporter.py`（确认 `_replace_stale_text` 透传 `synonyms`；不足则补）
- Modify: `backend/app/routers/bid.py`（导出端点用 `settings_store.get_placeholder_synonyms()` 供给）
- Test: `backend/tests/test_bid_placeholders.py` 或 `backend/tests/test_api_bid.py`（追加）

**背景**：Task 8a review 发现用户配置的同义词只影响预览端点；导出/校验路径 `fill_draft`/`verify_draft_fill` 仍走 `synonyms=None` → 默认库，违反 V1.2 4.5（同义词库须影响替换，且 fill 与 verify 共用同一基准）。

**Interfaces（Produces）：**
- `fill_draft(..., synonyms: dict | None = None)`：透传到 `_replace_stale_text(..., synonyms=...)` 与 `verify_draft_fill(replace_params={..., "synonyms": synonyms})`。
- 导出端点：`from app import settings_store`；`fill_draft(..., synonyms=settings_store.get_placeholder_synonyms())`（旧模板路径若也走替换，按需同样供给；不动无替换路径）。
- verify：`bid_verify.compute_text_subs(..., synonyms=params.get("synonyms"))`（Task 1 已实现读取）——确保填充与校验拿到同一 synonyms。

## 步骤
- [ ] Step 1: 写失败测试
  - `fill_draft` 传入 `synonyms={"甲方":"招标人"}`，底稿含 `甲方：____`（`甲方` 不是默认同义词）→ 产物被填、`verify.ok is True`；不传 synonyms 时同一底稿 `甲方：____` 不填。
  - 或经 API 测试：PUT 同义词库后导出，断言生效且 verify 通过（用 tmp 构造底稿+项目）。
- [ ] Step 2: 跑测试确认失败 → `python -m pytest tests/test_bid_placeholders.py tests/test_api_bid.py -q -k synonym`
- [ ] Step 3: 实现接线（规则仍只在 core，路由只供给 synonyms）。
- [ ] Step 4: 跑聚焦，再全量 `python -m pytest -q`（基线 334 passed）。
- [ ] Step 5: Commit `商务标：导出与校验接入占位符同义词库`

## 全局约束
- 后端工作目录 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\backend`，跑 `python -m pytest`。
- 填充端与校验端必须拿到同一 synonyms，避免防篡改误报。
- 不得在路由层复制规则；既有测试不回归。
- 英文标识符、中文文案；真实数据只读，测试程序化构造。
- 独立 commit，message 前缀 `商务标：`。
