# Task 6 报告：页码居中断言、静态目录分节与分节报告

## 实现内容（`app/core/bid_page_setup.py` 单文件）

1. **`is_static_toc_group(children) -> int | None`**（V1.2 7.5）：定位文本
   strip 后以「目录」开头的 `w:p`，其后连续 ≥2 个 `w:p` 文本匹配
   `r".+?[\.\s·…]{2,}\s*\d{1,4}\s*$"`（章节名＋页码形态）→ 返回目录组末
   元素下标；否则 None。双重特征缺一不可（防正文"目录"字样误判）。
2. **`check_footer_page_centered(docx_path) -> list[str]`**：解压产物全部
   `word/footer*.xml`，对含 PAGE 域（`w:instrText` 含 "PAGE"）的段落检查
   `pPr/jc@w:val`：
   - `center` → 通过；
   - 缺 `jc`（未显式设置）→ 安全补 `jc=center` 写回产物并复检（幂等）；
   - 显式非居中（有意设置）→ 不静默改，记告警（含 part 名/段落序号/jc 值）。
3. **`apply_page_setup` 扩展**：
   - `split_after` 优先 `is_static_toc_group(children)`（组后须有正文才拆节），
     无则回退现有 `_is_toc_el` 组逻辑（toc 样式/TOC 域，旧行为不变）；
   - 返回值增 `sections`（document.xml 中 sectPr 数）、`section_page_numbers`
     （逐节：挂 footerReference 且 pgNumType 重起）、`warnings`
     （= `check_footer_page_centered` 结果）；
   - 降级路径（参考缺失/无效）同样携带三个新键（默认值 1/[]/[]），行为不变。

## 测试（`tests/test_bid_page_setup.py` 追加 7 个）

- `test_is_static_toc_group_detected`（brief 原文 + 末下标断言）；
- `test_is_static_toc_group_requires_both_signals`（仅标题/仅页码段 → None）；
- `test_footer_page_centered_warns_when_left`（显式 jc=left → 告警含 footer）；
- `test_footer_page_centered_autofix_missing_jc`（缺 jc → 自动补正、无告警、
  幂等二次调用、产物 XML 实证 `jc=center`）；
- `test_footer_page_centered_ok_when_center`；
- `test_apply_page_setup_reports_sections`（静态目录分节端到端：sections≥2、
  节1 无引用、正文节 pgNumType start=1、warnings 空）；
- `test_apply_page_setup_degraded_still_reports_keys`（降级路径新键齐全）。

## TDD 证据

- **RED**：`python -m pytest tests/test_bid_page_setup.py -q -k "static or
  centered or sections"` → 收集期 `ImportError: cannot import name
  'check_footer_page_centered'`（接口未实现，预期失败）。
- **GREEN**：`python -m pytest tests/test_bid_page_setup.py -q` →
  `12 passed in 1.46s`（既有 5 + 新增 7）。
- **全量回归**：`python -m pytest -q` → `324 passed in 60.01s`（317 + 7）。

## 自审查

- brief 中"可安全修正则修正后复检（补/改 jc）"与测试
  `warns_when_left`（左对齐须告警）存在张力：若显式 left 也自动改，
  复检通过则无告警、测试必红。裁定：**缺 jc 补、显式非居中告警不改**
  ——缺省是"未设置"（补安全），显式值是"有意为之"（覆盖需人知）。
- 静态目录优先于 toc 样式路径；两者都命中时静态组优先（实测场景互斥，
  静态目录底稿无 toc 样式段）。
- `check_footer_page_centered` 独立 zip 读写，与 apply 的 `.p2tmp` 流程
  分离；临时文件 `.jctmp` 同名替换，幂等。
- 页脚匹配 `word/footer[^/]*\.xml` 同时覆盖 `footer1.xml`（Word 原生）与
  `footer_hxtd.xml`（移植 part）。
- YAGNI：未加"逐节 headerReference 明细"（brief 只要 sections/
  section_page_numbers/warnings 三键）。

## 关注点

- `section_page_numbers[i]` 语义 = 「挂页脚引用 **且** 页码重起」（按 brief
  原文）；单节文档（挂页脚但不重起）因此为 False——若前端想要"该节有无
  页码"语义需另行区分。
- 静态目录条目识别依赖点线/空格分隔符 ≥2 + 尾部数字；无分隔符的纯文本
  目录（如「第一章 概述 1」单空格）识别不到——符合 brief 给定正则。

## 提交

- `05e7fb9` 商务标：静态目录分节、页脚居中断言与分节报告
