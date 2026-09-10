# Task 2 报告：标段数据模型与导出参数

## 实现内容

1. **`app/db.py`**
   - 新增 `_migrate_projects_columns()`：仿 `_migrate_bid_templates_columns` 的
     `PRAGMA table_info` + 条件 `ALTER TABLE` 模式，为 `projects` 幂等补
     `section_name`/`section_no` 两列（`TEXT DEFAULT ''`）；在 `init_schema`
     现有三处迁移调用后追加调用（每次建库都执行）。
   - `update_project` 的 `allowed` 集合追加 `section_name`/`section_no`。
2. **`app/routers/bid.py`**
   - `BidTemplateExportIn` 新增 `section_name: str = ""`、`section_no: str = ""`。
   - `export_bid_template`：两字段 strip 后透传 `fill_draft`；非空时经
     `db.update_project` 持久化到 `projects`（下次导出可回显）。
   - 旧模板路径（无底稿回退）保持不传 section，行为不变。
3. **`app/core/bid_draft_exporter.py`**
   - `fill_draft` 签名追加 `section_name=""/section_no=""`；透传进
     `_replace_stale_text(...)` 与 `verify_draft_fill(replace_params={...,
     "section_name","section_no"})`——填充端与校验端同一套规则，verify 不误报。
4. **`app/core/bid_template_exporter.py`**
   - `_replace_stale_text` 签名追加 `section_name/section_no/synonyms` 并透传
     `compute_text_subs`（Task 1 已在 `compute_text_subs`/`build_placeholder_rules`
     加好签名，本任务补 `_replace_stale_text` 这一层透传）。
5. **`tests/test_api_bid.py`**：追加 3 个测试
   - `test_projects_has_section_columns`：迁移幂等 + 两列存在
     （brief 片段的 `db.conn` 在本 `Database` 类不存在，按现有 `_connect()`
     模式适配）。
   - `test_export_section_param_fills_label_and_bracket`：直接造底稿
     （`标段名称：____` + `（标段名称）`），导出带 section 参数 → 标签/括号
     均被填充、verify.ok=True、非空标段持久化到 projects。
   - `test_export_section_empty_skips_fill`：section 为空 → 占位保持原样、
     projects 标段列为空串。

## TDD 证据

- **RED**：`python -m pytest tests/test_api_bid.py -q -k section` →
  `3 failed`：`test_projects_has_section_columns`（列不存在）、
  `test_export_section_param_fills_label_and_bracket`（产物仍是 `标段名称：____`）、
  `test_export_section_empty_skips_fill`（`KeyError: 'section_name'`）。原因均为
  列/参数尚未实现，符合预期。
- **GREEN**：`python -m pytest tests/test_api_bid.py tests/test_bid_draft_export.py
  tests/test_api_bid_draft.py -q` → `54 passed in 16.19s`。
- **全量回归**：`python -m pytest -q` → `297 passed in 65.84s`（294 + 新增 3）。

## 自审查

- 完整性：brief Interfaces 全部产出（两列 / 两个模型字段 / fill_draft 透传
  + replace_params）。
- 对称性：`fill_draft` 的 section 参数同时进入 `_replace_stale_text` 与
  `verify_draft_fill(replace_params=...)`，测试断言 `verify.ok is True` 实证无误报。
- YAGNI：未改旧模板路径（`build_bid_docx_from_template` 不传 section，brief 允许）；
  未新增无用接口。
- 既有模式：迁移写法与 `_migrate_bid_templates_columns` 一致；测试复用
  `client`/`db_path`/`tmp_path` fixture 与 `_bid_url` 辅助。
- 测试输出干净，无 warning；测试全部程序化构造，未触碰真实数据。

## 关注点

- `update_project` 白名单新增两键：REST 层若有 `ProjectUpdate` 模型且不含
  section 字段，则只有导出端点会写这两列（当前行为即如此）；如后续需要项目
  编辑页直接维护标段，需在项目路由模型中另行暴露。
- brief 测试片段使用 `db.conn.execute(...)`，与 `Database` 实际的
  `_connect()` 模式不符，已按现有模式适配（功能等价）。

## 提交

- `8af9747` 商务标：标段字段+替换规则+导出参数
