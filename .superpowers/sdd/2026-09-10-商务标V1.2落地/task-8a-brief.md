# Task 8a: 后端前置端点（占位符预览 + 同义词 API）

**Files:**
- Modify: `backend/app/routers/bid.py` 或 `backend/app/routers/bid_draft.py`（占位符预览端点）
- Modify: `backend/app/routers/settings.py`（同义词 GET/PUT）
- Test: `backend/tests/test_api_bid_draft.py` / `tests/test_api_settings.py`（追加）

**背景**：Task 1 已实现 core `scan_placeholders(doc, params, synonyms=None)` 与 `settings_store.get_placeholder_synonyms()/save_placeholder_synonyms()`，但未建路由端点。计划 Task 8 前端「占位符确认」与 Task 9「同义词库设置页」依赖这两个端点。本任务补齐后端。

**Interfaces（Produces）：**
- 占位符预览：`POST /api/projects/{project_id}/bid-draft/placeholders`
  - body（字段全可选，默认 ""）：`project_no/project_name/doc_date/tenderer/bidder_name/section_name/section_no`
  - 行为：取该项目**当前底稿 docx**（同导出/`bid-draft` 预览所用的同一来源，如 `db.get_bid_template(project_id)` 的 draft 路径）；无底稿 → 404；否则 `from app.core.bid_template_exporter import scan_placeholders`，`synonyms=settings_store.get_placeholder_synonyms()`，返回 `{"matched":[...],"suspicious":[...]}`。
  - 若底稿来源不明，参照 `routers/bid_draft.py` 的 GET `/bid-draft` 预览取文件方式，保持一致。
- 同义词：
  - `GET /api/settings/placeholder-synonyms` → `settings_store.get_placeholder_synonyms()`（默认库含 `采购人→招标人` 等）
  - `PUT /api/settings/placeholder-synonyms`（body `{别名: 规范标签}`）→ `save_placeholder_synonyms`，返回规范化结果。

**注意**：`scan_placeholders` 的 params 键名必须与实现一致（读取 `bid_template_exporter.scan_placeholders`/`build_placeholder_rules` 确认，如 `project_name/tenderer/bidder_name/project_no/section_name/section_no/doc_date`）；缺失键不要传 None 导致报错。

## 步骤
- [ ] Step 1: 写失败测试
  - 预览端点：无底稿 404；有底稿且含 `招标人：____` → 返回 matched 含 `{"label":"招标人","value":<tenderer>}`（用 tmp 构造底稿并挂到项目，参照 `test_api_bid_draft.py` 现有底稿 fixture）。
  - 同义词：GET 默认含 `采购人→招标人`；PUT 自定义后 GET 回读一致。
- [ ] Step 2: 跑测试确认失败 → `python -m pytest tests/test_api_bid_draft.py tests/test_api_settings.py -q -k "placeholder or synonym"`
- [ ] Step 3: 实现两个端点（复用 `scan_placeholders` / settings_store，勿重复实现规则）。
- [ ] Step 4: 跑聚焦，再全量 `python -m pytest -q`（当前基线 330 passed）。
- [ ] Step 5: Commit `商务标：占位符预览与同义词API端点`

## 全局约束
- 后端工作目录 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\backend`，跑 `python -m pytest`。
- 规则只经 `scan_placeholders`/`build_placeholder_rules`，不得在路由层复制规则。
- 无底稿返回 404，不改动导出路径；既有测试不回归。
- 英文标识符、中文文案；真实数据只读，测试程序化构造。
- 独立 commit，message 前缀 `商务标：`。
