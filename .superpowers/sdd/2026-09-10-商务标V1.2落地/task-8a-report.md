# Task 8a 报告：后端前置端点（占位符预览 + 同义词 API）

## 实现内容

1. **`app/routers/bid_draft.py`**
   - `PlaceholderPreviewIn`：`project_no/project_name/doc_date/tenderer/
     bidder_name/section_name/section_no` 全可选默认 `""`（与
     `scan_placeholders` 的 params 键名逐一核对一致）。
   - `POST /api/projects/{project_id}/bid-draft/placeholders`：取底稿方式与
     GET `/bid-draft` 预览一致（`db.get_project_bid_template(project_id)`
     的 `file_path`）；无行或文件不存在 → 404；否则
     `scan_placeholders(doc, params, synonyms=settings_store
     .get_placeholder_synonyms())` 原样返回 `{"matched","suspicious"}`。
     规则零复制。
2. **`app/routers/settings.py`**
   - `GET /api/settings/placeholder-synonyms` → `get_placeholder_synonyms()`
     （默认库 + 已存覆盖项）。
   - `PUT /api/settings/placeholder-synonyms`（body `{别名: 规范标签}`）→
     `save_placeholder_synonyms`，返回清洗后的覆盖项。
3. **测试**
   - `tests/test_api_bid_draft.py`：无底稿 404；程序化底稿（`招标人：____`）
     挂项目后预览 matched 含 `{"label":"招标人","value":"某中心"}` 且
     `suspicious` 键存在。
   - `tests/test_api_settings.py`：GET 默认含 `采购人→招标人`/
     `工程项目名称→项目名称`；PUT 自定义（空键被清洗）→ 回读一致且
     默认库不丢。

## TDD 证据

- **RED**：`python -m pytest tests/test_api_bid_draft.py
  tests/test_api_settings.py -q -k "placeholder or synonym"` →
  `4 failed`（两端点 404/缺键）。
- **GREEN**：`python -m pytest tests/test_api_bid_draft.py
  tests/test_api_settings.py -q` → `29 passed in 10.13s`。
- **全量回归**：`python -m pytest -q` → `334 passed in 60.16s`
  （330 基线 + 新增 4）。

## 自审查

- 规则只在 core：路由层仅做参数透传 + 404 映射，未复制任何匹配逻辑。
- `body=None`（空请求体）容忍：`params={}` → scan 内部 `params.get` 全部
  回落空串，无 None 传入。
- 未触碰导出路径；无底稿语义按 brief 用 404（注意同文件 PUT bindings 的
  无底稿是 422，两处语义不同属有意区分：预览=资源不存在）。
- YAGNI：未加 DELETE/单条删除端点（Task 9 前端如需再议）。

## 关注点

- `PlaceholderPreviewIn` 不带 `synonyms` 键——同义词恒取全局设置（brief
  指定行为）；调用方无法按请求覆盖。
- PUT 同义词为「覆盖项」语义（save 的是覆盖层，GET 合并默认库）；前端
  清空某条需 PUT 全量覆盖集（无单条删除）。

## 提交

- `aaf8602` 商务标：占位符预览与同义词API端点
