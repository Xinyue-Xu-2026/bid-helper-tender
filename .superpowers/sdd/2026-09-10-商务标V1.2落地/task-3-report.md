# Task 3 报告：图片自适应插入、失败显式化与降采样

## 实现内容

1. **`app/core/bid_template_exporter.py`**（新增"图片等比自适应插入"区块）
   - `measure_image_cm(image_path)`：Pillow 读图，96dpi 换算 `(w_cm, h_cm, ratio)`，
     打不开/无 Pillow/尺寸为 0 → `None`。
   - `fit_image_cm(image_path, avail_w_cm, avail_h_cm=24.0, fallback_w_cm=7.0)`：
     读不出尺寸 → 退化固定宽度（`degraded="无法读取图片尺寸，退化为固定宽度"`）；
     否则 `w=min(avail_w, w0)`、`h=w/ratio`，`h>avail_h` 再压宽并 `too_long=True`。
   - `insert_image_adaptive(container, ...)`：container 支持 `Paragraph`/`_Cell`；
     文件不存在 → `{"ok":False,"reason":"图片文件不存在"}`；`max(im.size)>3000`
     → `thumbnail((2000,2000))` 存 BytesIO PNG 再插入；插入异常 →
     `{"ok":False,"reason":"插入失败：..."}`（无静默吞异常）。
   - `cell_available_width_cm(cell, default=14.0)`：`tblGrid/gridCol` 求和
     （python-docx 解析为 EMU Length，`/360000` 换算，已实测 `Cm(6)`→`w=2160270`），
     回退 `tcW`（dxa 缇 `/567`），再回退 default。
   - `page_text_width_cm(doc, default=16.0)`：页宽 - 左右边距。
   - `_insert_image_into_table(table, image_path, report=None, table_index=None,
     person="", label_kind="")`：改用 `insert_image_adaptive`（fallback 8.0cm 保持
     旧视觉）；report 非空时按 `{"table_index","person","label_kind","ok",
     "reason","too_long"}` 记入 `report["images"]`；无 report 的旧调用
     （`_insert_person_images`）签名兼容。
2. **`app/core/bid_draft_exporter.py`**
   - `_fill_image_slots`：删除自带的存在性判断与手工 append，改调
     `_insert_image_into_table(..., report=report, ...)`——文件缺失等失败现在
     显式记入 `images[].reason`。
   - 授权页 `_append_images`：移除 `except Exception: pass`，改用
     `insert_image_adaptive`（可用宽=`page_text_width_cm(doc)`，退化宽=
     `_ID_CARD_WIDTH.cm`=7.0cm），每次尝试（含失败）记入 `report["images"]`
     （`table_index=None, label_kind="身份证"`）；`authority_images` 计数语义不变
     （仅 ok 时 +1）。
3. **`requirements.txt`**：追加 `Pillow>=10`（环境实测已装 Pillow 12.3.0）。
4. **测试**
   - 新建 `tests/test_bid_images.py`（brief 原文 5 个用例）。
   - 更新 `tests/test_bid_draft_export.py::test_image_slot_insert` 的期望 dict：
     原断言是**精确字典相等**，`report["images"]` 条目新增 `reason`/`too_long`
     两键必须同步（行为无回归：ok=True、画图仍存在）。

## TDD 证据

- **RED**：`python -m pytest tests/test_bid_images.py -q` → 收集期
  `ImportError: cannot import name 'fit_image_cm' from 'app.core.bid_template_exporter'`
  （接口未实现，预期失败）。
- **GREEN**：`python -m pytest tests/test_bid_images.py tests/test_bid_draft_export.py
  tests/test_bid_draft_authority.py tests/test_bid_template.py -q` →
  `37 passed in 12.27s`。
- **全量回归**：`python -m pytest -q` → `302 passed in 68.23s`（297 + 新增 5）。

## 自审查

- 完整性：brief Interfaces 五项函数全部产出；测试为 brief 原文。
- 静默异常：目标处（`_append_images` 的 `except Exception: pass`、
  `_fill_image_slots` 的存在性静默跳过）已移除；新增代码中三处
  `except Exception` 均有显式返回/回退值（measure→None、降采样→按原图插入、
  页宽→default），非静默。`bid_page_setup.py` 等其他模块的既有 except 不在
  本任务范围，未动。
- 兼容性：`_insert_image_into_table` 无 report 调用不崩（旧路径
  `_insert_person_images` 未改）；`fill_draft` 既有测试仅一处精确字典断言需同步。
- commit 包含 brief 未列出的 `tests/test_bid_draft_export.py`（断言同步必需，
  否则既有测试红）。

## 关注点

- `cell_available_width_cm` 按 brief 对 gridCol **求和**：1 列图片占位表等价于
  单元格宽；若未来多列表格插图，该值会是整表宽（偏大）。当前 image_slot/
  授权页场景无此用法。
- 身份证图片的可用宽从固定 7cm 变为页正文宽（默认 16cm）——小图不放大
  （`w=min(avail, w0)`），大图按页宽等比缩放，视觉效果只会更贴合；既有授权
  测试（图片计数）全绿。
- 降采样失败回退为按原图插入（不阻断导出），失败仅在插入阶段显式入报告。

## 提交

- `30d46f5` 商务标：图片等比自适应、失败报告与Pillow降采样
