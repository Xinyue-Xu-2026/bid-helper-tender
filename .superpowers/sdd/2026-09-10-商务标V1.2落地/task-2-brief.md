# Task 2: 标段数据模型与导出参数

**Files:**
- Modify: `backend/app/db.py`（`init_schema` 内加 `_migrate_projects_columns`）
- Modify: `backend/app/routers/bid.py`（`BidTemplateExportIn` + 导出调用处）
- Modify: `backend/app/core/bid_draft_exporter.py`（`fill_draft` 增 `section_name/section_no`）
- Modify: `backend/app/core/bid_template_exporter.py`（`_replace_stale_text`/`compute_text_subs` 透传 section 参数——Task 1 已加签名，本任务确认旧模板路径也透传或按需）
- Test: `backend/tests/test_api_bid.py`（追加）

**Interfaces:**
- Consumes: Task 1 `build_placeholder_rules` 的 `section_name/section_no`（已实现；`compute_text_subs` 与 `build_placeholder_rules` 已接受 `section_name/section_no/synonyms`）。
- Produces:
  - `projects.section_name` / `projects.section_no` 两列（幂等迁移，`TEXT DEFAULT ''`）。
  - `BidTemplateExportIn.section_name: str = ""`, `.section_no: str = ""`。
  - `fill_draft(..., section_name="", section_no="")`，并把这两个字段透传进 `_replace_stale_text` 与 `verify_draft_fill` 的 `replace_params`。

## 步骤

- [ ] **Step 1: 写失败测试**

```python
def test_projects_has_section_columns(client):
    from app.db import Database
    db = Database(); db.init_schema(); db.init_schema()   # 幂等
    cols = {r[1] for r in db.conn.execute("PRAGMA table_info(projects)")}
    assert {"section_name", "section_no"} <= cols


def test_export_section_param_fills_label_and_bracket(client, ...):
    # 构造底稿含 "标段名称：____" 与 "（标段名称）"，导出 body 带 section_name/section_no，
    # 断言产物文本被替换；section 为空则跳过（不进报告 filled）
    ...
```
（若既有测试用 `client` fixture；如无，按 `tests/conftest.py`/`test_api_bid_draft.py` 现有模式构造。）

- [ ] **Step 2: 跑测试确认失败** → `python -m pytest tests/test_api_bid.py -q -k section`
  Expected: FAIL

- [ ] **Step 3: 实现**

`db.py`：仿 `db.py:141-147` 的 `PRAGMA table_info` + 条件 `ALTER TABLE ... ADD COLUMN` 模式新增：
```python
def _migrate_projects_columns(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(projects)")}
    for name in ("section_name", "section_no"):
        if name not in cols:
            conn.execute(f"ALTER TABLE projects ADD COLUMN {name} TEXT DEFAULT ''")
```
并在 `init_schema` 现有三处迁移调用处追加调用（确保每次建库都执行）。

`routers/bid.py`：`BidTemplateExportIn` 加 `section_name: str = ""`、`section_no: str = ""`；导出端点把两字段透传到创建底稿/填充调用；若数据库 `update` 有对应方法，非空时持久化到 `projects`。

`bid_draft_exporter.fill_draft`：签名追加 `section_name="", section_no=""`；`_replace_stale_text(...)` 与 `verify_draft_fill(..., replace_params={...,"section_name":section_name,"section_no":section_no})` 透传。

`bid_template_exporter._replace_stale_text` / `compute_text_subs`：确认已接受并透传 `section_name/section_no`（Task 1 已加）；旧模板路径 `build_bid_docx_from_template` 可保持不传（无标段），除非测试要求。

- [ ] **Step 4: 跑测试** → `python -m pytest tests/test_api_bid.py tests/test_bid_draft_export.py tests/test_api_bid_draft.py -q`
  Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/app/routers/bid.py backend/app/core/bid_draft_exporter.py backend/app/core/bid_template_exporter.py backend/tests/test_api_bid.py
git commit -m "商务标：标段字段+替换规则+导出参数"
```

## 全局约束

- 后端工作目录 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\backend`，跑 `python -m pytest`。
- 迁移必须幂等（老库自动补列，重复 init 不报错）。
- 填充端与校验端共用规则；`fill_draft` 的 `section_name/section_no` 必须同时进入 `replace_params`，保证 verify 不误报。
- 英文标识符、中文文案；不改旧模板导出路径既有行为；真实数据只读，测试程序化构造。
- 独立 commit，message 前缀 `商务标：`。
