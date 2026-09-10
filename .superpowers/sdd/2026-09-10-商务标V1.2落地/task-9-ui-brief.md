# Task 9（前端）：设置页占位符同义词库

**Files:**
- `frontend/src/views/SettingsView.vue`
- `frontend/src/api/index.js`（若 Task 8 未加，则加 `getPlaceholderSynonyms`/`savePlaceholderSynonyms`）
-（校验：`npm run build` 绿）

**设计者职责**：布局/视觉/交互由你决定，须与 SettingsView 既有区块（模型设置/导入配置/字段配置）风格一致；中文文案、响应式可用。

## 已就绪的后端契约
- `GET /api/settings/placeholder-synonyms` → `{别名: 规范标签}`（默认库含 `采购人→招标人`、`工程项目名称→项目名称`、`工程名称→项目名称`、`供应商名称→投标人名称`）
- `PUT /api/settings/placeholder-synonyms`（body `{别名: 规范标签}`，**全量覆盖**语义）→ 返回规范化结果
- 规范标签可选值（用于下拉）：`项目名称`、`招标人`、`投标人名称`、`项目编号`、`招标编号`、`标段名称`、`标段编号`、`日期`

## 需求
- 新增「占位符同义词」区块：表格 `别名 → 规范标签`（规范标签为下拉选择），支持增行、删行、编辑、保存。
- 保存调用 `savePlaceholderSynonyms`（全量覆盖集合）；保存后以服务端返回为准刷新。
- 说明文案：提示"别名用于底稿中与规范标签不同的写法；导出与校验共用同一同义词库"。
- 空别名/空标签的行不提交（或保存前校验提示）。
- 无新增依赖；`npm run build` 绿；不改后端。

## 全局约束
- 文案与既有设置页一致；英文标识符中文文案。
- 独立 commit：`商务标：设置页占位符同义词库`。
- 报告写至 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\.superpowers\sdd\2026-09-10-商务标V1.2落地\task-9-report.md`。
