# Task 8（前端）报告：商务标导出占位符确认、标段输入与报告渲染

## 变更文件

### 1. `frontend/src/api/index.js`
- 新增 `previewBidPlaceholders(pid, payload)` → `POST /projects/{pid}/bid-draft/placeholders`，body 含 `project_no / project_name / doc_date / tenderer / bidder_name / section_name / section_no`。
- 新增 `getPlaceholderSynonyms()` / `savePlaceholderSynonyms(mapping)` → `GET/PUT /settings/placeholder-synonyms`（供 Task 9 设置页使用）。
- `exportBidTemplate` 注释更新：payload 补充说明 `section_name` / `section_no`（函数本身透传 payload，无需改动逻辑）。
- `saveBidDraftBindings` 注释更新：行模型补充 `header_rows`(1..4) 与 `mode`(`''`/`per_person`) 字段说明。

### 2. `frontend/src/components/BidPanel.vue`

**A. 导出对话框（导出商务标）**
- 对话框宽度 440px → 560px，容纳新增输入与占位符确认区。
- 表单新增「标段名称」「标段编号」两个可选输入（placeholder 注明"可留空"），`exportForm` 初始化与导出 payload 同步带上 `section_name` / `section_no`（trim 后提交）。
- 新增「占位符确认」区（表单下方，虚线分隔）：
  - 打开对话框时（表单值回填完成后）自动调 `previewBidPlaceholders`；提供「重新预览」按钮。
  - **将填入**：`matched` 逐项 `标签 → 值`，`count > 1` 时标注"填充 N 处"；空值显示"（空）"。
  - **未识别（疑似占位）**：`suspicious` 列表用警示色（#e6a23c），附提示"导出后将保留原样，请人工核对"。
  - 「按默认填充，跳过确认」链接：折叠确认区并显示降级说明，可再点「查看确认」展开。
  - 优雅降级：无底稿或请求失败时显示 info 提示条"暂无法预览占位符……不影响导出"（拦截器弹错一次，对话框内不阻塞导出按钮）。

**B. 绑定确认表（底稿预览与确认对话框）**
- 对话框宽度 760px → 900px，容纳新增列。
- 角色选项新增 `resume_each`（简历表（每人一份）），与 `lead_resume` 区分；`lead_resume` 保持原样。
- 新增「表头行数」列：`el-input-number`（1..4，small），随保存提交、随 `getBidDraft` 回显（`applyDraftPreview` 拷贝行时补齐缺省值 `header_rows=1`、`mode=''`）。
- `resume_each` 行的「条件」列：「每人一张表」复选框（`mode=per_person` 开关）+ 预览文案「每人一张表 × N 人」（N = 当前已勾选人员数，实时联动）；关闭时显示"已关闭每人一张表，按单表填充"。
- `onBindingRoleChange`：切到 `resume_each` 时默认 `mode='per_person'`，切走清空 `mode`。
- 保存 payload 每行补 `header_rows`（数值兜底 ≥1）与 `mode`（仅 `resume_each` 且为 `per_person` 时提交，其余提交 `''`）。
- `columns` 与既有列确认控件未改动。

**C. 导出填充报告对话框**
- **占位符**：`placeholders.filled` 逐项 `标签 → 值`（count>1 标注）；`placeholders.suspicious` 警示色列表 + 人工核对提示。
- **图片失败**：`ok:false` 项红色加粗显示 `reason`（无 reason 时显示"未知原因"），`too_long` 追加"（扫描件过长，建议拆分）"。
- **页码/分节**：显示 `sections`（分节数）；`section_page_numbers` 为数组时逐节显示"第 N 节：已挂页码/未挂页码"；`degraded` 非空时显示降级原因警示条；`warnings` 逐条警示条渲染。

## 设计决策
- 占位符确认放在导出对话框内而非独立弹窗：减少一次点击跳转，确认结果与填写表单同屏对照，符合流程①"填表 → 确认 → 导出"的线性动线。
- 「跳过确认」只做 UI 折叠（不改变导出行为），因为导出本身始终按表单值填充；跳过的语义是"不再逐项核对"。
- 失败降级用 info 而非 warning：无底稿是合法状态（旧模板路径），不应恐吓用户；错误弹窗仍由全局拦截器负责一次。
- `resume_each` 的每人一张表用复选框 + 实时人数预览，让"× N 人"的后果在勾选前可见。
- 报告对话框沿用既有 `h4 + 13px 列表` 的排版节奏，新增分区保持同样间距（12px 上外边距），警示色沿用 Element Plus 语义色（#e6a23c / #f56c6c）。

## 验证
- `npm run build` 通过（vite build 成功，无新增编译错误；仅有既有的 chunk 体积提示）。
- 未验证（需后端联调）：占位符预览接口在无底稿时的确切错误码、导出响应头 `X-Fill-Report` 中 `page_setup.section_page_numbers` 的具体结构（前端按布尔数组防御性渲染）、`resume_each`/`header_rows` 的实际填充效果。
- 未做任何后端改动。

## 跟进修复

1. **图片 too_long 提示位置**：`insert_image_adaptive` 在插入成功但高度被截顶时也会返回 `too_long: true`（"扫描件过长，建议拆分"的主要场景）。原实现把提示放在 `ok:false` 分支内，成功行永远不显示。已将提示移出 `im.ok` 判断，成功/失败行均渲染；成功行用警示橙（#e6a23c）、失败行保持红（#f56c6c），以区分"已插入但截顶"与"插入失败"。
2. **header_rows 上限兜底**：绑定保存 payload 的 `header_rows` 增加 `Math.min(4, ...)` 上限钳制（保留原有 `>=1` 下限兜底），防止异常值触发后端 422。
- 修复 commit：`商务标：修复图片过长提示与表头行数兜底`；`npm run build` 通过。
