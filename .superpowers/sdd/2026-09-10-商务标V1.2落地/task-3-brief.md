# Task 3: 图片自适应插入、失败显式化与降采样

**Files:**
- Modify: `backend/app/core/bid_template_exporter.py`（`_insert_image_into_table` 增加自适应+报告）
- Modify: `backend/app/core/bid_draft_exporter.py`（授权页与占位表图片 `_append_images`/`_fill_image_slots`）
- Modify: `backend/requirements.txt`（增 Pillow）
- Test: `backend/tests/test_bid_images.py`（新建）

**Interfaces:**
- Produces:
  - `measure_image_cm(image_path) -> (w_cm, h_cm, ratio) | None`（Pillow；失败返回 None）
  - `fit_image_cm(image_path, avail_w_cm, avail_h_cm=24.0, fallback_w_cm=7.0) -> {"width_cm","height_cm","degraded","too_long"}`
  - `insert_image_adaptive(container, image_path, avail_w_cm, avail_h_cm=24.0, fallback_w_cm=7.0) -> {"ok","reason","too_long","degraded"}`
    （container 可为 `Paragraph` 或 `Cell`）
  - `cell_available_width_cm(cell, default=14.0) -> float`（读 `tblGrid`/`tcW`）
  - `page_text_width_cm(doc, default=16.0) -> float`
- Consumes: Task 1 已完成，无需 placeholder 交互。

## 步骤

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_bid_images.py
from PIL import Image
from docx import Document
from app.core.bid_template_exporter import (
    fit_image_cm, insert_image_adaptive, cell_available_width_cm)

def _png(path, w, h):
    Image.new("RGB", (w, h), "white").save(path)

def test_fit_image_limits_by_height(tmp_path):
    p = tmp_path / "tall.png"; _png(p, 400, 4000)   # 10:1 竖长
    r = fit_image_cm(str(p), avail_w_cm=7.0, avail_h_cm=24.0)
    assert r["height_cm"] <= 24.0 + 1e-6
    assert r["width_cm"] < 7.0
    assert r["too_long"] is True

def test_fit_image_uses_cell_width_when_wide(tmp_path):
    p = tmp_path / "wide.png"; _png(p, 2000, 1000)
    r = fit_image_cm(str(p), avail_w_cm=7.0, avail_h_cm=24.0)
    assert abs(r["width_cm"] - 7.0) < 1e-6
    assert abs(r["height_cm"] - 3.5) < 0.01

def test_insert_reports_missing_file(tmp_path):
    doc = Document(); cell = doc.add_table(1, 1).rows[0].cells[0]
    r = insert_image_adaptive(cell, str(tmp_path / "nope.png"), 6.0)
    assert r["ok"] is False and "不存在" in r["reason"]

def test_insert_reports_unsupported_format(tmp_path):
    f = tmp_path / "x.emf"; f.write_bytes(b"not an image")
    doc = Document(); cell = doc.add_table(1, 1).rows[0].cells[0]
    r = insert_image_adaptive(cell, str(f), 6.0)
    assert r["ok"] is False and r["reason"]

def test_cell_width_from_tblgrid(tmp_path):
    from docx.shared import Cm
    doc = Document(); t = doc.add_table(1, 1); t.columns[0].width = Cm(6)
    assert 5.5 < cell_available_width_cm(t.rows[0].cells[0]) < 6.5
```

- [ ] **Step 2: 跑测试确认失败** → `python -m pytest tests/test_bid_images.py -q`，Expected: FAIL

- [ ] **Step 3: 实现**
  - `requirements.txt` 增 `Pillow>=10`；`pip install Pillow`。
  - `measure_image_cm`：`Image.open(path)` → `w,h=im.size`；按 96dpi 换算 `cm = px/96*2.54`；异常返回 None。
  - `fit_image_cm`：无 Pillow/打不开 → `{"width_cm":fallback,"height_cm":0,"degraded":"无法读取图片尺寸，退化为固定宽度","too_long":False}`；否则 `w=min(avail_w, w0)`、`h=w/ratio`；若 `h>avail_h` → `h=avail_h, w=h*ratio, too_long=True`。
  - `insert_image_adaptive(container, ...)`：容器为 `Paragraph` 或 `Cell`（cell → `cell.paragraphs[0]`）。文件不存在 → `{"ok":False,"reason":"图片文件不存在"}`。按需 Pillow 降采样：`max(im.size)>3000` → `im.thumbnail((2000,2000))` 存 `BytesIO` PNG 再插入。插入：`try: para.add_run().add_picture(src, width=Cm(w), height=Cm(h)); ok=True except Exception as e: ok=False, reason=f"插入失败：{e}"`。**禁止 bare except: pass**。
  - `cell_available_width_cm`：遍历 `cell._tc` 所在 `w:tbl` 的 `w:tblGrid/w:gridCol` 求和（EMU→cm：`/360000`），回退 `tcW`，都不取则 default。
  - 改造 `_insert_image_into_table(table, image_path, report=None, table_index=None)`：调用 `insert_image_adaptive`，把结果按 `{"table_index","person","label_kind","ok","reason","too_long"}` 记入 `report["images"]`（保留旧无 report 调用兼容）。
  - `bid_draft_exporter._append_images`：移除 `except Exception: pass`，记录失败原因（`report["images"]` 明细）。授权页身份证图片保持 `_ID_CARD_WIDTH` 作 fallback 宽度，但改用自适应。

- [ ] **Step 4: 跑测试** → `python -m pytest tests/test_bid_images.py tests/test_bid_draft_export.py tests/test_bid_draft_authority.py tests/test_bid_template.py -q`，Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/app/core/bid_template_exporter.py backend/app/core/bid_draft_exporter.py backend/tests/test_bid_images.py
git commit -m "商务标：图片等比自适应、失败报告与Pillow降采样"
```

## 全局约束
- 后端工作目录 `D:\00工作+学习\宏信天德\投标助手\投标Web平台\backend`，跑 `python -m pytest`。
- 移除静默 `except: pass`；失败必须记入报告 `images[].reason`。
- 保持旧调用兼容（`_insert_image_into_table` 无 report 调用不崩）；既有测试不回归。
- 英文标识符、中文文案；真实数据只读，测试程序化构造（Pillow 造图）。
- 独立 commit，message 前缀 `商务标：`。
