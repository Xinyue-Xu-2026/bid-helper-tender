# Task 6: 页码居中断言、静态目录分节与分节报告

**Files:**
- Modify: `backend/app/core/bid_page_setup.py`
- Test: `backend/tests/test_bid_page_setup.py`（追加）

**Interfaces:**
- Produces:
  - `is_static_toc_group(children) -> int | None`（返回目录组末元素下标）
  - `check_footer_page_centered(docx_path) -> list[str]`（返回告警列表，空=通过）
  - `apply_page_setup(docx_path)` 返回增 `{"sections": int, "section_page_numbers": [bool], "warnings": [str]}`

## 背景（V1.2 7.5）
- 页码居中已由参考页脚保证（XML 验证 jc=center），但需**程序化断言**产物页脚 PAGE 域所在段落居中，不满足即告警。
- 目录识别现仅认 `toc` 样式/TOC 域；静态文本目录（标题「目录」＋「章节名＋页码」段组）识别不到 → 不分节 → 封面挂页眉页码、正文页码未从 1 起。
- 导出校验需输出分节数、各节页眉页脚引用、pgNumType。

## 步骤

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_bid_page_setup.py 追加
import zipfile
from docx import Document
from app.core.bid_page_setup import (
    apply_page_setup, check_footer_page_centered, is_static_toc_group)


def test_is_static_toc_group_detected():
    from lxml import etree
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = etree.fromstring(
        f'<w:body xmlns:w="{W}">'
        '<w:p><w:r><w:t>投标文件封面</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>目录</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>第一章 概述 ........ 1</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>第二章 方案 ........ 5</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>正文开始</w:t></w:r></w:p></w:body>')
    children = list(body)
    idx = is_static_toc_group(children)
    assert idx is not None


def test_footer_page_centered_warns_when_left(tmp_path):
    # 构造含左对齐 PAGE 域的 docx 页脚，断言返回非空告警
    ...


def test_apply_page_setup_reports_sections(tmp_path):
    # 含静态目录的产物 apply_page_setup 后 sections>=2，正文节 page_numbers True
    # 参考文件缺失时 degraded 分支不受影响
    ...
```

- [ ] **Step 2: 跑测试确认失败** → `python -m pytest tests/test_bid_page_setup.py -q -k "static or centered or sections"`

- [ ] **Step 3: 实现**
  - `is_static_toc_group(children)`：定位段落文本 strip 后 `== "目录"`（或 `startswith("目录")`）的 `w:p`，其后连续 ≥2 段文本匹配 `r".+?[\.\s·…]{2,}\s*\d{1,4}\s*$"`（章节名＋页码形态），返回该连续组末下标；否则 None。
  - `apply_page_setup` 的 `split_after`：优先用 `is_static_toc_group(children)`；无则回退现有 `_is_toc_el` 组逻辑（保持旧行为）。
  - `check_footer_page_centered(docx_path) -> list[str]`：解压产物全部 `word/footer*.xml`，对含 PAGE 域（`w:instrText` 含 "PAGE"）的段落检查 `w:pPr/w:jc@w:val == "center"`；不满足 → 告警串（含 part 名/段落序号）。可安全修正则修正后复检（补/改 jc）。返回告警列表。
  - `apply_page_setup` 末尾调 `check_footer_page_centered`，把告警并入 `result["warnings"]`；统计 `document.xml` 的 `w:sectPr` 数量为 `sections`；逐节是否有 footerReference 且 restart → `section_page_numbers`。
  - 参考缺失降级路径（`degraded`）行为不变；zip 后置处理保持幂等。

- [ ] **Step 4: 跑测试** → `python -m pytest tests/test_bid_page_setup.py -q`；再全量 `python -m pytest -q`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/bid_page_setup.py backend/tests/test_bid_page_setup.py
git commit -m "商务标：静态目录分节、页脚居中断言与分节报告"
```

## 全局约束
- 后端工作目录 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\backend`，跑 `python -m pytest`。
- 保持既有 page_setup 5 个测试全绿（封面+目录节无页眉无页码、正文页码从 1）。
- 参考文件缺失/无效必须继续降级不报错；不得破坏导出。
- 静态目录识别需"目录标题＋后接页码形态段组"双重特征，避免正文出现"目录"字样标题误判。
- 英文标识符、中文文案；真实数据只读，测试程序化构造 docx。
- 独立 commit，message 前缀 `商务标：`。
