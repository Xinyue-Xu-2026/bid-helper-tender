# 投标Web平台 设计文档

- 日期：2026-08-19
- 状态：已获用户确认（含两处补充）
- 项目位置：`D:\00工作+学习\宏信天德\投标助手\投标Web平台\`
- 参考对象：小羊标书（xiaoyangbiaoshu.com）
- 功能迁移来源：`D:\00工作+学习\宏信天德\投标助手\投标APP\`（bidhelper，PyQt6 桌面应用）

---

## 1. 背景与目标

为公司投标部建设一个本地单机使用的 Web 标书平台，对标小羊标书的核心链路，迁移现有桌面 APP 已实现的「招标文件解析」能力，并按投标部实际工作习惯扩展。

与小羊标书的差异化：
- 支持废标项/符合性核对（小羊标书没有）
- 解析结果六类结构化（资质门槛/评分项/废标项/格式要求/时间节点/其他），比小羊标书的浅层提取更细
- 本地单机，数据不出本机

## 2. 已确认需求

| 项 | 结论 |
|---|---|
| 部署形态 | 本地 Web 单机使用，无账号权限体系 |
| 技术栈 | 后端 FastAPI（Python 3.10+）+ 前端 Vue3 + Vite + Element Plus + SQLite |
| AI 服务 | Kimi API，照搬现有双网关逻辑（sk-kimi- 前缀识别、失败回退、temperature/max_tokens 差异、截断重试） |
| 模板角色 | v1 = 写作范例参考（内容风格+样式供 AI 仿写）；通过 TemplateStrategy 抽象预留「骨架填充」等模式扩展口 |
| 废标项检查 | v1 人工打钩核对，数据层预留 AI 自动比对字段 |
| 交付节奏 | 分两期（见第 8 节） |

### v1 功能清单
1. 项目管理（CRUD）
2. 招标文件解析（迁移现有功能，SSE 流式进度）
3. 企业资产库：企业信息 / 资信证书 / 常用人员 / 素材库
   - **支持 Excel 批量导入**（用户补充①）
   - **证书（资质、人员证书等）有效期提前 30 天提醒**（用户补充②）
4. 废标项/符合性人工核对
5. 项目资料上传（PDF / 图片 / Word / Excel）
6. 模板上传（docx）
7. 正文 AI 编写（引用模板+素材+招标要求，单节生成/重写）
8. 导出：Excel（一期）、Word（二期，保持模板字体/字号/样式）

## 3. 架构

```
D:\00工作+学习\宏信天德\投标助手\
├── 投标APP\            ← 现有桌面版，保持不动
└── 投标Web平台\        ← 本项目
    ├── backend/
    │   ├── core/       从 bidhelper 拷贝的解析核心
    │   │   ├── extractor.py     PDF(PyMuPDF)/DOCX(python-docx) 文本抽取
    │   │   ├── llm_parser.py    Kimi LLM 解析（含 SYSTEM_PROMPT，核心资产）
    │   │   ├── parser.py        规则解析兜底
    │   │   └── postprocess.py   去重与模板噪声过滤
    │   ├── routers/    projects / tender / assets / write / export / compliance
    │   ├── services/   业务编排（含 BidService 逻辑迁移）
    │   ├── models.py   SQLite 数据访问层
    │   └── main.py     FastAPI 入口，托管 API + 前端静态文件
    ├── frontend/       Vue3 + Vite + Element Plus SPA
    ├── data/
    │   ├── app.db
    │   ├── uploads/    招标文件与项目资料
    │   ├── templates/  模板 docx
    │   └── materials/  素材库文件
    ├── tests/
    └── start.bat       一键启动 uvicorn，浏览器访问 localhost:8000
```

关键决策：
- **解析核心以拷贝方式复用**（非跨目录引用），原桌面 APP 不受影响，两边各自演进
- **修正硬编码路径**：bidhelper `config.py` 的 `APP_ROOT` 绝对路径改为基于项目 `data/` 的相对路径
- 单机单进程，uvicorn 托管 API 与构建后的前端静态文件，无需 nginx/服务器运维

## 4. 数据模型（SQLite）

| 表 | 关键字段 | 说明 |
|---|---|---|
| `projects` | id, name, tender_file_path, template_id, notes, created_at | 项目 |
| `requirements` | id, project_id, category, content, source, confidence, status | 解析要求条目（沿用 bidhelper 六分类与字段） |
| `assets` | id, type, name, fields(JSON), file_path, expiry_date, created_at | 企业资产库；type ∈ info / credit / person / material；**expiry_date 用于有效期提醒** |
| `materials` | id, project_id, file_path, file_type, created_at | 项目级上传资料（PDF/图片/Word/Excel） |
| `templates` | id, name, file_path, mode, created_at | 写作模板；mode 标记模板策略 |
| `sections` | id, project_id, parent_id, title, level, content, gen_status, order | 编写产物（章节树，二期） |
| `compliance_checks` | id, project_id, requirement_id, checked, checked_at, ai_result, ai_confidence | 废标核对；ai_* 字段 v1 预留不用 |

## 5. 页面结构（仿小羊标书导航裁剪）

- **工作台**：项目列表、新建项目；**顶部横幅/铃铛展示 30 天内到期证书提醒**
- **项目-招标文件**：上传 PDF/DOCX → SSE 流式解析 → 要求清单（六类筛选、搜索、状态内联编辑、导出 Excel）
- **资产库**（四个页签）：
  - 企业信息：结构化表单（名称、信用代码、地址、法人、开户行等）
  - 资信证书：图片/文件上传 + 名称/发证机关/有效期字段；**Excel 批量导入**；到期前 30 天标红提醒
  - 常用人员：姓名、身份证号、职称、证书及有效期；**Excel 批量导入**；证书到期前 30 天提醒
  - 素材库：文件上传（PDF/图片/Word/Excel），供编写引用
- **废标检查**：废标项+资质门槛清单逐条打钩，进度统计（已核对 x/y）
- **编写工作台**（二期）：目录树 → 按章节 AI 生成（注入招标要求+模板范例+勾选素材）→ 单节重新生成
- **导出**：Excel（一期）；Word（二期，python-docx 基于模板生成，保持模板样式）

## 6. 关键设计点

1. **SSE 流式**：解析与 AI 生成均走 SSE，进度实时可见（小羊标书核心体验）
2. **TemplateStrategy 抽象**：`class TemplateStrategy: def build_prompt(template, ...) -> str`；v1 实现 `ExampleReferenceStrategy`（提取模板内容风格+样式描述供 AI 仿写）；后续可加 `SkeletonFillStrategy` 等，即"留口子"
3. **废标核对扩展口**：`compliance_checks` 预留 `ai_result/ai_confidence`；服务端预留 `POST /api/compliance/{project_id}/ai-check` 路由占位
4. **有效期提醒**：后端启动时 + 每日检查 `assets.expiry_date`，30 天内到期的进入提醒列表 API；前端工作台横幅+资产库标红
5. **Excel 导入**：openpyxl 读取，首行列名映射，错误行跳过并汇总提示（复用 bidhelper excel 相关经验）
6. **Word 导出**：python-docx 读取模板 docx 的样式定义，生成内容套用模板字体/字号/标题样式

## 7. 错误处理与测试

- 解析失败自动回退规则解析（沿用现有逻辑）；LLM 超时/限流返回明确错误信息
- 上传文件类型/大小校验；不支持扫描件解析时明确提示
- 后端：bidhelper 现有 16 个 pytest 测试随核心模块迁移适配 + 新增 API 层测试
- 前端：关键流程手动验证清单（上传→解析→清单→核对→导出）

## 8. 分期交付

**一期（先跑通可用）**
- 项目 CRUD
- 招标文件解析迁移（含 SSE 进度）
- 要求清单页 + Excel 导出
- 资产库四模块（含 Excel 导入、有效期 30 天提醒）
- 废标项人工核对

**二期**
- 模板上传 / 项目资料上传
- 正文 AI 编写工作台（单节生成/重写）
- Word 导出（保持模板样式）

## 9. 非目标（YAGNI）

- 账号体系 / 权限 / 多人协作
- 积分、充值、邀请裂变等商业化功能
- 扫描件 OCR 解析（与小羊标书同样明确不支持）
- AI 废标自动比对（仅预留接口）
- 移动端适配
