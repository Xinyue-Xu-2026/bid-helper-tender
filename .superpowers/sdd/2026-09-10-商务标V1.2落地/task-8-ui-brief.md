# Task 8（前端）：商务标导出占位符确认、标段输入与报告渲染

**Files:**
- `frontend/src/api/index.js`
- `frontend/src/components/BidPanel.vue`
-（校验：`npm run build` 必须绿）

**设计者职责**：布局/视觉/交互由你决定，须与既有 BidPanel 面板风格一致；中文文案、响应式可用。

## 已就绪的后端契约（务必按此对接）

1. `POST /api/projects/{pid}/bid-draft/placeholders`
   - body：`{project_no, project_name, doc_date, tenderer, bidder_name, section_name, section_no}`（均可空）
   - 返回：`{"matched":[{"label":"招标人","value":"某中心","count":1,"kind":"label"}], "suspicious":[{"text":"______"}]}`
2. 导出 `POST /api/projects/{pid}/bid-assets/export-template`（`responseType: blob`）body 支持新增 `section_name`、`section_no`。
3. 绑定保存 `PUT /api/projects/{pid}/bid-draft/bindings`：每个 table 行支持
   - `header_rows`（int 1..4，表头行数）
   - `mode`（`""` 或 `"per_person"`；`"per_person"` = 简历表每人一张）
   既有字段：`table_index, role, columns, person_scope, perf_scope, label_kind, person, confirmed`。
4. 底稿预览 `GET /api/projects/{pid}/bid-draft` 返回 bindings（含 `header_rows`/`mode` 建议值）；分类器新增角色 `resume_each`（简历表-每人一份，与 `lead_resume` 区分）。
5. 导出响应头 `X-Fill-Report`（JSON）现含：
   - `filled[]`、`skipped[]`、`verify{ok,issues,...}`
   - `images[{table_index,person,label_kind,ok,reason,too_long}]`（失败 `ok:false` + `reason`）
   - `page_setup{sections, section_page_numbers, warnings[], header_applied, page_numbers, degraded}`
   - `placeholders{filled:[{label,value,count,kind}], suspicious:[{text}]}`

## 需求

### A. `api/index.js`
- 新增 `previewBidPlaceholders(pid, payload)` → `POST .../bid-draft/placeholders`（JSON）。
- 绑定保存 payload 每行补 `header_rows`、`mode`；行模型同步（`getBidDraft` 回显）。
- `exportBidTemplate` payload 补 `section_name`、`section_no`。
- 新增 `getPlaceholderSynonyms()` / `savePlaceholderSynonyms(m)`（供 Task 9 设置页使用）：`GET/PUT /api/settings/placeholder-synonyms`。

### B. 导出对话框
- 在既有「项目编号/项目名称/招标人/投标人/法定代表人/委托代理人/日期」基础上，新增「标段名称」「标段编号」两个可选输入。

### C. 占位符确认（V1.2 4.3 / 流程①）
- 打开导出对话框（或点击「预览占位符」）时调 `previewBidPlaceholders`（用当前表单值），展示：
  - **将填入**：`matched` 逐项 `标签 → 值`（count>1 可标注）；
  - **未识别（疑似占位）**：`suspicious` 列表，警示色，提示需人工核对；
  - 提供「一键全默认/跳过」；无底稿或请求失败时优雅降级（提示但不阻塞导出）。

### D. 绑定确认表（7.1 / 7.4 / 7.6）
- 每行显示并可编辑 `header_rows`（数字输入，1..4），随保存提交、随 `getBidDraft` 回显。
- 对 `resume_each` 行显示「每人一张表 × N 人」预览（N=当前勾选人员数），并提供 `mode=per_person` 的开启控件（默认按建议值；用户可关）。`lead_resume` 保持原样。
- 确保 `columns`（含 role 列）与既有列确认控件不被破坏。

### E. 报告对话框（V1.2 4.3 / 流程②）
在既有「已填充/图片/已跳过/校验」基础上增加：
- **占位符**：`placeholders.filled` 逐项 `标签 → 值`；`placeholders.suspicious` 警示列表；
- **图片失败**：`images` 中 `ok:false` 项显著展示 `reason`（红），`too_long` 提示"扫描件过长，建议拆分"；
- **页码/分节**：`page_setup.sections`（分节数）、`section_page_numbers`（各节是否挂页码）、`warnings` 列表；`degraded` 非空时提示降级原因。

## 全局约束
- `frontend/` 工作目录；`npm run build` 必须成功（无新增编译错误）。
- 不改后端；不破坏既有导出/绑定/预览交互与既有字段。
- 文案用词与既有界面一致；避免英文裸词。
- 独立 commit：`商务标：前端导出占位符确认、标段输入与报告渲染`。
- 报告写至 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\.superpowers\sdd\2026-09-10-商务标V1.2落地\task-8-report.md`。
