# 投标Web平台 二期设计文档

- 日期：2026-08-19
- 状态：设计已经用户分节确认，待 spec 审阅
- 项目位置：`D:\00工作+学习\宏信天德\投标助手\投标Web平台\`
- 前置文档：`docs/specs/2026-08-19-投标web平台-design.md`（一期设计，已确认）
- 重要背景：桌面版 bidhelper 在二期三个方向（模板/编写/Word 导出）**无任何既有实现**（已侦察确认），二期从零设计；可复用的仅为已拷贝的 LLM 基础设施（`backend/app/core/llm_parser.py` 的双网关、错误翻译、模型路由）与 `extractor.py` 的 docx 遍历经验。

---

## 1. 范围

**三项核心功能**
1. 模板上传（docx）+ 项目资料上传（PDF/图片/Word/Excel）
2. 正文 AI 编写工作台（章节树 + 单节生成/重写 + 人工编辑）
3. Word 导出（保持模板字体/字号/标题样式，含目录 TOC 域）

**Minor 清债**：一期终审裁决「留二期」的全部条目，见第 9 节。

## 2. 已确认决策（brainstorming Q&A）

| 项 | 结论 |
|---|---|
| 二期范围 | 三项核心 + Minor 清债 |
| 章节树来源 | AI 根据招标要求生成目录初稿（格式要求+评分项为主），用户增删改定稿 |
| 资产注入 | 全部按节勾选：结构化资产（企业信息/常用人员/资信证书字段）与素材库文件均作为生成面板勾选项 |
| 正文编辑形态 | 纯文本 textarea 编辑；标题样式由章节树 level 自动映射，正文套模板正文样式 |
| Word 目录页 | 导出时插入 Word 原生 TOC 域，用户在 Word 里「更新域」生成目录 |
| 生成管线 | 方案一：风格画像复用 + 单节 SSE 生成 |

## 3. 架构与模块

后端新增（沿用一期分层，包内路径均相对 `backend/`）：

| 模块 | 职责 |
|---|---|
| `app/core/template_strategy.py` | `TemplateStrategy` 抽象（`build_prompt(template, ...) -> str`）+ v1 实现 `ExampleReferenceStrategy`；预留 `SkeletonFillStrategy` 等扩展 |
| `app/core/template_analyzer.py` | 模板风格画像：extractor 读 docx 全文 → 一次 LLM 调用 → 画像文本（写作风格/常用句式/结构特征/样式描述）。LLM 调用沿用 `client` 参数注入设计（可 mock） |
| `app/core/outline_generator.py` | 目录大纲初稿：输入=项目要求清单（格式要求+评分项为主，其余分类摘要）→ LLM 输出章节树 JSON（含 level 层级） |
| `app/core/section_writer.py` | 单节正文生成：组装 prompt → SSE 流式输出 |
| `app/core/word_exporter.py` | Word 导出：复制模板 styles.xml 建新文档 → 章节树 level 映射 Heading 1/2/3 → 正文套模板正文样式 → 文首插 TOC 域 |
| `app/routers/templates.py` | 模板上传/列表/删除/画像重试 |
| `app/routers/materials.py` | 项目资料上传/列表/删除 |
| `app/routers/write.py` | 章节树 CRUD、大纲生成、单节生成 SSE |
| `app/routers/export.py` | 新增 Word 导出端点 |
| `app/services/write_service.py` | 编写流程编排（对齐一期 `bid_service` 模式） |

前端：
- 项目详情页新增「资料与模板」区（模板上传+画像状态、项目资料上传/列表/删除）
- 新增独立路由页 `/projects/:id/write`：编写工作台

## 4. 数据模型（SQLite 新增三表）

| 表 | 字段 | 说明 |
|---|---|---|
| `templates` | id, name, file_path, mode, style_profile, created_at | **全局模板库**（不属单一项目，多项目复用；上传入口虽在项目详情页但入全局库，导出时从库中选定）。mode 标记模板策略（v1 恒为 `example`）；style_profile 为画像文本，NULL=未分析/失败 |
| `materials` | id, project_id, file_path, file_type, created_at | 项目级上传资料 |
| `sections` | id, project_id, parent_id, title, level, content, gen_status, sort_order | 章节树；gen_status ∈ 未生成/生成中/已生成/已编辑 |

老库兼容：三表走 `init_schema()` 的 `CREATE TABLE IF NOT EXISTS`，既有 `app.db` 启动自动补建，无迁移脚本。

## 5. 核心流程

### 5.1 模板上传 → 风格画像
1. 项目详情页「资料与模板」区上传 docx → 存 `data/templates/`，登记 templates（mode=`example`）
2. 上传后同步触发画像分析（前端 loading，单次 LLM 调用，数十秒）
3. 成功：画像写入 style_profile；失败：style_profile 置 NULL + 「重试」按钮，**不阻塞模板后续使用**（生成时无画像则退化为纯要求驱动，并在生成面板提示）

### 5.2 项目资料上传
同区上传（PDF/图片/Word/Excel）→ 存 `data/uploads/` → 登记 materials。支持列表与删除。

### 5.3 编写工作台（`/projects/:id/write`，三栏布局）

```
┌─────────────┬──────────────────────┬─────────────────┐
│ 章节树       │ 正文编辑区            │ 生成面板          │
│ (el-tree    │ (textarea 纯文本)     │ · 勾选企业信息/人员│
│  增删改/拖拽) │ [保存]               │   /证书/素材      │
│ · AI 生成目录│                      │ · 本节关联要求预览  │
│   初稿       │                      │   （可增删勾选）   │
│             │                      │ · [生成]/[重写]   │
└─────────────┴──────────────────────┴─────────────────┘
```

1. 首次进入无章节 → 「AI 生成目录初稿」→ outline_generator 输出落库 → 用户增删改/拖拽定稿
2. 选中叶子节 → 右栏勾选资产与素材 → 关联要求按「章节标题与要求 content 关键词重叠」自动预匹配、用户可增删 → 「生成」→ SSE 流式追加到编辑区 → 人工润色 → 「保存」
3. 重写 = 清空本节内容重新生成（**不保留历史版本**，YAGNI）
4. gen_status 流转：未生成 → 生成中 → 已生成 →（用户编辑保存后）已编辑

### 5.4 Word 导出
工作台「导出 Word」→ 选定模板（样式来源）→ 后端读模板 styles.xml 建新文档 → level 映射 Heading 1/2/3、正文套模板正文样式 → 文首插 TOC 域 → 下载 `{项目名}_标书.docx` → 用户在 Word 右键目录「更新域」生成页码。

## 6. 关键设计点

1. **SSE 事件契约**（对齐一期解析 SSE 模式）：单节生成事件流为 `chunk`（data=文本增量）→ 终态 `done`（data=全量文本）或 `error`（data=友好错误文案，载荷剥离换行符防分帧破坏）
2. **单节生成 prompt 组装**：目录标题链（全章节标题，保证节间衔接）+ 本节关联要求 + 风格画像（可空）+ 勾选资产/素材文本（素材文件经 extractor 抽文本，图片仅注入文件名与备注）
3. **画像一次性成本**：模板上传时分析一次存库，生成时零额外 LLM 调用
4. **TemplateStrategy 抽象**：v1 仅 ExampleReferenceStrategy；接口预留骨架填充等后续模式
5. **Word 样式保真**：以模板 styles.xml 为样式库，标题按 level 映射模板 Heading 样式，正文用模板默认正文样式；不逐段复制模板内容格式（v1 不做骨架填充）
6. **临时文件与上传安全**：沿用一期白名单校验；模板仅 docx，资料限 PDF/图片/Word/Excel

## 7. 错误处理

- LLM 错误一律经 `_friendly_api_error` 翻译（401/限流/截断等）
- SSE 生成中断：已流出内容保留在编辑区但**不自动落库**，用户自行决定保存或重写，不污染已存内容
- Word 导出前置校验：章节树为空禁止导出；模板已删除或样式缺失时回退 python-docx 默认样式并明确提示
- 画像失败可重试；无画像生成时给出提示但不阻断

## 8. 测试策略

- 后端 pytest：
  - core 单测：画像/大纲的 LLM 返回 JSON 解析（含坏 JSON 分支）、section_writer prompt 组装断言（目录链/要求/画像/勾选资产均在 prompt 中）、word_exporter 断言 styles.xml 复制与 TOC 域存在
  - API 层测试：templates/materials/write/export 新端点（LLM 一律 client 注入 mock，零网络）
- 前端：手动验证清单（同一期模式）
- 验收：全部 pytest 通过 + `npm run build` 成功 + start.bat 全流程走查（含二期链路：传模板→画像→传资料→生成目录→单节生成→编辑保存→导出 Word→Word 更新域出目录）

## 9. Minor 清债清单（一期终审裁决留二期）

| 组 | 条目 |
|---|---|
| 前端错误处理 | axios 全局响应拦截器统一 ElMessage（覆盖 T13/T14 无错误处理）；删除确认弹窗（要求/资产/项目）；confirm 取消 rejection 处理；form 重置；就地编辑后刷新统计；EventSource onUnmounted 清理；created_at 显示格式化 |
| 后端健壮性 | 临时文件清理三处（upload/导出/import）；SPA 兜底对未知 `/api/*` 返回 404；SSE error 载荷剥离换行；PUT 要求六分类枚举校验；保存要求先删后插包事务；导出文件名项目名 sanitize；删资产时清理附件孤儿文件；`on_event` 迁 lifespan；ai-check 占位 404 语义修正；projects.py 注释与行为不符修正 |

## 10. 非目标（YAGNI）

- 封面/页眉页脚（用户在 Word 自行完善）
- 正文历史版本
- AI 废标自动比对（仍仅预留接口）
- 账号体系/权限/多人协作
- 富文本编辑、Markdown
- 模板骨架填充（SkeletonFillStrategy 仅留抽象口）
