# Task 1 报告：占位符规则核心（含文本框遍历与校验对称）

## 实现内容

1. **`app/core/bid_template_exporter.py`**
   - 新增常量：`DEFAULT_PLACEHOLDER_SYNONYMS`、`PLACEHOLDER_LABEL_KEYS`、`BRACKET_LABEL_KEYS`、`_SECTION_COMBO_RE`、`_UNRECOGNIZED_UNDERSCORE_RE`、`_DOC_DATE_BLANK_RE`、`_PLACEHOLDER_ONLY_RE`（均按 brief 给定值）。
   - 新增 `_effective_label_keys(synonyms)`、`_date_text(doc_date)`。
   - 新增 `_iter_textbox_paragraphs(doc)`（`w:txbxContent` 内段落 + 嵌套表格单元格段落，不重复）；`_iter_all_paragraphs` 扩展为 正文 + 表格 + 文本框。
   - 新增 `build_placeholder_rules(...)`：顺序 stale → 组合 → 标签（长度降序）→ 括号（长度降序）→ 日期；每项 `{"kind","label","key","value","pattern","repl"}`。
   - `compute_text_subs` 改为 `build_placeholder_rules` 的 `(pattern, repl)` 投影，签名追加 `section_name/section_no/synonyms`（默认空，旧位置调用兼容）。旧 `_TENDERER_LABEL_RE`/`_BIDDER_LABEL_RE` 保留未删。
   - 新增 `scan_placeholders(doc, params, synonyms=None)` → `{"matched":[{label,value,count,kind}], "suspicious":[{text}]}`。
2. **`app/core/bid_verify.py`**
   - 新增 `_textbox_texts(doc, subs=None)`；`verify_draft_fill` 的 `compute_text_subs` 调用补 `section_name/section_no/synonyms`；末尾追加文本框对称比对（数量不一报数量，逐段不等报下标，issue 文案含"文本框内容被改动"）。
3. **`app/settings_store.py`**
   - 追加 `get_placeholder_synonyms()` / `save_placeholder_synonyms(m)`（按 brief 代码，默认库来自 `DEFAULT_PLACEHOLDER_SYNONYMS`）。
4. **`tests/test_bid_placeholders.py`**：按 brief 原文新建（4 个测试）。

## TDD 证据

- **RED**：`python -m pytest tests/test_bid_placeholders.py -q`
  输出：`ImportError: cannot import name 'DEFAULT_PLACEHOLDER_SYNONYMS' from 'app.core.bid_template_exporter'`（收集阶段 1 error）。原因：新接口尚未实现，符合预期失败。
- **GREEN**：`python -m pytest tests/test_bid_placeholders.py tests/test_bid_verify.py tests/test_bid_template.py -q` → `24 passed in 8.88s`。
- **全量回归**：`python -m pytest -q` → `292 passed in 59.54s`。

## 与 brief 的偏差（两处，均为让给定测试通过所必需）

1. **组合规则 repl 用半角括号**：brief 实现要点写 `f"{project_name}（{section_name}）"`（全角），但给定测试 `test_bracket_half_and_full_width_filled` 同时断言 `"P (S)" in full` 且 `"（" not in full`——全角 repl 必然使两者失败。测试为 brief 给定代码、实现要点为"实现以满足测试"，故采用 `f"{project_name} ({section_name})"`。**后续任务若依赖全角组合输出需留意此处。**
2. **标签循环跳过 `doc_date` 键**：`日期` 标签若走通用标签规则会先吃掉 `____` 导致 `_DOC_DATE_BLANK_RE` 失配（得到 `日期：2026-09-10年__月__日`），故日期仅由专用日期规则（带数字 + 空白年月日）处理。括号循环中 `doc_date` 键的值也经 `_date_text` 归一化。
3. **stale 名称守卫**：`_discover_stale_values` 会把 `项目名称：____` 的 `____` 识别为旧项目名，stale 规则会抢先替换所有 `____`（包括"采购人：____"），导致标签规则失效。新增 `_PLACEHOLDER_ONLY_RE` 守卫：stale_name 全为下划线/空白时不生成 stale_name 规则。对旧路径是行为改进（旧逻辑在此种底稿上会误替换），旧测试全绿。

## 自审查

- 完整性：brief 列出的接口全部产出；测试为 brief 原文；commit message 与 brief 一致。
- YAGNI：未添加 brief 之外的接口；`scan_placeholders` 仅实现测试与 brief 要求的字段。
- 既有模式：复用 `_iter_cell_paragraphs`/`_para_text`/`_is_toc_paragraph`；verify 侧与导出侧共用同一 `compute_text_subs`，坐标系一致。
- 测试输出干净（无 warning/failure）；未触碰真实数据，测试全部程序化构造。

## 关注点

- 组合规则 repl 半角/全角问题（见偏差 1），建议控制器定夺是否回改测试或接受现状。
- `settings_store.py` 中新 import 位于模块中部（按 brief 片段位置），无循环导入（bid_template_exporter 不依赖 settings_store）。
- `_replace_stale_text` 现会处理文本框段落（随 `_iter_all_paragraphs` 扩展），verify 侧 `_textbox_texts` 已对称豁免；未绑定文本框被外部改动时现在会报"文本框内容被改动"（新增校验维度，属预期）。

## 提交

- `35ef158` 商务标：通用占位符规则核心（标签/括号/日期/文本框+校验对称）

## 修复轮 1

### 变更内容

1. **Important 1（文本框重复产出）**：`_iter_textbox_paragraphs` 跳过 `mc:Fallback` 内的 `w:txbxContent`（新增 `_MC_FALLBACK_TAG` 常量，`iterancestors` 判定）。Word 真实文件中文本框为 `mc:AlternateContent`（Choice=DrawingML + Fallback=VML，各含一份相同 txbxContent），修复前段落产出两次。验证：临时脚本对标准 AlternateContent 构造裸跑 `body.iter(qn("w:txbxContent"))` 计数为 2（确认测试非空转），修复后 `_iter_textbox_paragraphs` 产出 1 次。新增测试 `test_textbox_alternate_content_fallback_not_duplicated`。
2. **Important 2（组合括号风格）**：`_SECTION_COMBO_RE` 增加捕获组——组 1=首组开括号、组 2=两组间空白、组 3=标段组开括号；repl 改为函数，保留底稿括号风格与组间空白：半角输入 `(项目名称) (标段名称)` → `P (S)`，全角输入 `（项目名称）（标段名称）` → `P（S）`。比裁定建议多保留了组间空白（否则既有半角断言 `"P (S)"` 中的空格会丢失）。新增测试 `test_section_combo_keeps_full_width_brackets`。
3. **Minor 3**：`verify_draft_fill` docstring 的 `replace_params` 说明补 `tenderer/bidder_name/section_name/section_no/synonyms`。

### 覆盖测试

- 命令：`python -m pytest tests/test_bid_placeholders.py tests/test_bid_verify.py tests/test_bid_template.py -q`
  输出：`26 passed in 10.56s`（原 24 + 新增 2）
- 命令：`python -m pytest -q`
  输出：`294 passed in 68.91s`（全量无回归）

### 提交

- `5e2e7ad` 商务标：修复占位符文本框重复与组合括号风格
