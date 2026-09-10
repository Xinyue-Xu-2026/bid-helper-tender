# Task 9a 报告：导出端接入占位符同义词库（后端）

## 实现内容

1. **`app/core/bid_draft_exporter.py`**：`fill_draft` 新增
   `synonyms: dict = None` 入参；透传到 `_replace_stale_text(...,
   synonyms=synonyms)`（Task 2 已支持该形参，本次确认无需补）与
   `verify_draft_fill(replace_params={..., "synonyms": synonyms})`
   （Task 1 已在 verify 端读取 `params.get("synonyms")`）——填充与校验
   拿到同一份同义词库，防篡改不误报。docstring 同步。
2. **`app/routers/bid.py`**：导出端点 `fill_draft(...,
   synonyms=settings_store.get_placeholder_synonyms())`（含默认库的合并
   结果）。旧模板回退路径不涉及 synonyms（该路径不接收同义词，未动）。
3. **测试**
   - `tests/test_bid_placeholders.py::test_fill_draft_synonyms_fill_alias`：
     core 级——`synonyms={"甲方":"招标人"}` + `tenderer="某中心"` 时
     `甲方：____` 被填且 `verify.ok is True`；不传 synonyms 时不填。
   - `tests/test_api_bid.py::test_export_uses_placeholder_synonyms`：API
     级——PUT 同义词库后 export-template，产物含 `甲方：某中心` 且
     X-Fill-Report 的 verify.ok 为真。

## TDD 证据

- **RED**：`python -m pytest tests/test_bid_placeholders.py
  tests/test_api_bid.py -q -k synonym` → `2 failed`（core：fill_draft 无
  synonyms 形参 TypeError；API：`甲方：____` 未被填充）。
- **GREEN**：聚焦 `-k synonym` → `2 passed`；扩大聚焦
  （placeholders + api_bid + draft_export）→ `48 passed in 8.60s`。
- **全量回归**：`python -m pytest -q` → `336 passed in 60.18s`
  （334 基线 + 新增 2）。

## 自审查

- 规则零复制：路由仅供给 synonyms dict；匹配/替换逻辑全在 core。
- 对称性：fill 与 verify 共用同一 `synonyms` 对象（同一表达式传入两处），
  API 测试实证 verify.ok。
- 注意 `_effective_label_keys` 语义：`synonyms` 非空时**替换**默认库而非
  合并——core 直接调用方（如测试）传自定义 dict 时默认别名失效；API 路径
  经 `get_placeholder_synonyms()`（合并默认库）无此问题。属 Task 1 既定
  语义，未改。
- commit 未含 `bid_template_exporter.py`（`git add` 列入但该文件无 diff——
  `_replace_stale_text`/`compute_text_subs` 的 synonyms 透传在 Task 1/2
  已就位）。

## 关注点

- 预览端点（Task 8a）与导出端现在都经 `get_placeholder_synonyms()`，
  预览所见即导出所得。
- 旧模板路径（无底稿回退）不接同义词——该路径 `_replace_stale_text`
  调用方 `build_bid_docx_from_template` 未传 synonyms（用默认库）；
  如需对齐可后续一行加上，本任务 brief 未要求（"不动无替换路径/按需"）。

## 提交

- `1db1d30` 商务标：导出与校验接入占位符同义词库
