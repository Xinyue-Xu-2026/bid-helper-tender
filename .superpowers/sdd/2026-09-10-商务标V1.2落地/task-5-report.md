# Task 5 报告：简历表「一人一表」整表克隆（核心）

## 实现内容

1. **`app/core/bid_table_classifier.py`**
   - `ROLES` 增 `"resume_each"`；新增 `RESUME_EACH_MARKERS =
     ("拟在本项目任职","主要工作经历","执业资格证书名称")`。
   - 新规则排在 `lead_resume` 之前：表格 2~5 列、`RESUME_LABELS` 命中 ≥3 个
     不同标签、且第 0 列文本含任一标记 → `resume_each`（columns 同
     `_match_resume` 产出）；不满足标记的旧样表仍落 `lead_resume`（向后兼容）。
   - 建议项 dict 增 `"mode": ""` 默认键。
2. **`app/services/bid_service.py`**
   - 抽出模块级 `_perf_lines_for(name, contracts)`（复用原 lead_lines 逻辑：
     `fields["项目负责人"]==姓名` → `项目名称（年份）`）。
   - `assemble_bid_draft_data` 每个 person 增 `perfs_text`；`lead_perfs_text`
     保留 = 负责人的 `perfs_text`。
3. **`app/core/bid_draft_exporter.py`**
   - `_clone_table_after(table)`：`deepcopy(table._tbl)` + `addnext`
     （tbl → 克隆 → 空段分隔），XML 级克隆保留行列/合并/行高/样式。
   - `_fill_resume_table` 第 4 参改名 `perfs_text`（随人传入）。
   - `fill_draft` 新增 `resume_each` 分支：`mode=="per_person"` 时按
     `person_scope` 取人，先全部克隆（基于填充前样表，链式 addnext 保序）
     再逐人填充，每人 `perfs_text = p["perfs_text"] or (lead 时
     lead_perfs_text)`；`report["filled"]` 记 `cloned=len(picked)`；
     `table_insertions[idx] = len(picked)-1` 传入 verify。无 per_person →
     退化单份 lead 填充（旧行为）。`lead_resume` 分支同样优先用
     `lead["perfs_text"]`。bound 角色元组加 `"resume_each"`。
   - `_auth_signature_block` 段坐标系改「非空段」（见下"坐标系决策"）。
4. **`app/core/bid_verify.py`**
   - `verify_draft_fill(..., table_insertions: dict = None)`：产物表数 =
     底稿表数 + Σinsertions；底稿表下标经位移映射（`draft_to_out`）到产物表
     比对，克隆表无底稿对应仅计入数量等式。
   - 段落比对两侧增过滤「空段」（`_para_text` 为空）——见下。
5. **`app/services/bid_draft_service.py`**：`_BINDING_KEYS` 增 `"mode"`
   （preview 回显/归一化自动覆盖）。
6. **`app/routers/bid_draft.py`**：`TableBindingIn.mode: str = ""`；
   校验 `mode ∈ {"", "per_person"}`，非法 422。
7. **测试**：新建 `tests/test_bid_resume_clone.py`（5 个：克隆计数/逐人填充/
   verify 不误报/cloned 报告、结构保留（行列/合并/行高）、无 mode 退化、
   分类器 resume_each vs lead_resume、7.3 donor vMerge 剔除回归）；
   `test_bid_draft_service.py` 增 `perfs_text` 逐人用例；
   `test_api_bid_draft.py` 增 mode 校验+回显用例。

## 坐标系决策（实现中发现，brief 未覆盖）

克隆表分隔空段是**新增正文段落**，会打破 verify 的段落数量等式与
`bound_paragraph_indices`（授权页）坐标系。方案：段落比对坐标系统一为
「toc/分节符/**空段**过滤后的非空段序列」——

- 空段不携带内容，增删不构成内容篡改（防篡改目标不变）；
- 分隔空段天然豁免，无需额外登记参数；
- 填充端 `_auth_signature_block` 的 bound 下标改用同一坐标系后，克隆插入
  空段不再使授权页下标位移（顺序无关）。
- 既有断言（`checked_paragraphs == 3` 等）所涉底稿均无空段，不受影响；
  全量 315 测试实证无回归。

另：行高断言改为与底稿自身落盘值比较（`Cm(1.5)` 经 twips 取整为 539750
EMU，非精确 540000）——克隆保真以 XML 级一致为准。

## TDD 证据

- **RED**：`python -m pytest tests/test_bid_resume_clone.py -q` →
  `4 failed, 1 passed`（resume_each 角色/克隆/perfs_text/mode 均未实现；
  vMerge 用例一次通过——`_strip_tr_vmerge` 既有能力，作回归保留）；
  服务/API 两新用例同 RED（`KeyError: 'perfs_text'` / `KeyError: 'mode'`）。
- **GREEN**：`python -m pytest tests/test_bid_resume_clone.py
  tests/test_bid_draft_export.py tests/test_bid_verify.py
  tests/test_bid_draft_service.py tests/test_api_bid_draft.py
  tests/test_bid_classifier.py tests/test_bid_draft_authority.py -q` →
  `87 passed in 16.69s`。
- **全量回归**：`python -m pytest -q` → `315 passed in 57.88s`（308 + 新增 7）。

## 自审查

- 结构保真：deepcopy `_tbl` 非重建；测试实证行列数/横向合并（同 _tc）/
  行高（与底稿同值）保留。
- 对称性：`table_insertions` 由填充端产生、校验端消费，同一登记；
  `report["verify"]["ok"] is True` 在 2 个克隆用例中实证。
- 兼容：无 `mode=per_person` → 单份 lead 填充（专门用例）；旧 bindings
  无 `mode` 键 → `binding.get("mode")` 为 None → 旧行为；`lead_perfs_text`
  旧键保留。
- YAGNI：brief 建议的 `clone_idx` 集合未实现——下标位移映射已天然跳过
  克隆表，该集合无消费方。
- 首次 GREEN 跑出的 2 个失败（段落数量等式、行高取整）均如实修复，
  未改测试放水（行高改为与底稿同值比较，语义更强）。

## 关注点

- 空段豁免是策略性变化：纯空段增删（非我方克隆产生）不再触发校验告警。
  已在上面的"坐标系决策"说明理由；若控制器要求更严，可改为显式
  `paragraph_insertions` 登记（实现成本更高）。
- `resume_each` 建议项 `mode` 默认为空（不自动开一人一表），前端需在用户
  确认绑定后显式选择；如需分类器对 resume_each 默认建议 `mode="per_person"`，
  一行即可加（本任务未要求）。
- 多个 `resume_each` 绑定同表不同 scope 的场景未覆盖（同一 table_index
  绑定两次本就不在 schema 语义内）。

## 提交

- `42d325a` 商务标：简历表一人一表整表克隆（含校验登记）

## 修复轮 1

### 变更内容

1. **Important（克隆表相邻合并）**：`_clone_table_after` 改为
   `tbl.addnext(sep); sep.addnext(new)`——分隔空段插入链尾表与克隆之间
   （旧实现 `addnext(sep); addnext(new)` 使空段落全部积压在克隆链尾部，
   产生 TBL,TBL,TBL 相邻序列，Word 会合并渲染为一张表）；克隆后若紧跟
   兄弟仍是表（哨兵表场景）再补一个链尾空段。fill 调用链显式以链尾
   （上一份克隆）为下一份的 anchor。结果序列 `T0, sep, C1, sep, C2, ...`。
   修复轮评审指出的该缺陷此前测试测不出（旧测试只数 `len(out.tables)`）。
2. **回归测试 ×2**（`tests/test_bid_resume_clone.py`）：
   - `test_no_adjacent_tables_after_clone`：3 人克隆后遍历产物 body
     `iterchildren()`，断言无相邻 `w:tbl` 兄弟。
   - `test_clone_shift_mapping_sentinel_table`：底稿 [样表, 哨兵表] 克隆
     2 人 → 产物哨兵表内容保留（位移映射穿透）；篡改哨兵表 →
     `verify_draft_fill(..., table_insertions={0:1})` 报 `表格[1]`。
3. **Minor 2（docstring）**：`verify_draft_fill` 段落过滤注释补充——
   仅含图片（无文本）的段落同属空段、不参与段落比对（已知豁免）。
4. 编辑事故：追加测试时误吞 `test_fill_strips_vmerge_from_donor` 的
   def 行，已立即恢复并经测试确认。

### 覆盖测试

- 命令：`python -m pytest tests/test_bid_resume_clone.py
  tests/test_bid_verify.py tests/test_bid_draft_export.py
  tests/test_bid_draft_authority.py -q` → `37 passed in 6.62s`
- 命令：`python -m pytest -q` → `317 passed in 59.79s`（315 + 新增 2，无回归）

### 提交（修复轮 1）

- `ccdb7d6` 商务标：修复克隆简历表相邻合并（表间分隔）

## 跟进：resume_each 默认 mode

- 变更：分类器 `resume_each` 建议项 `mode` 由 `""` 改为 `"per_person"`
  （V1.2 7.4 / 验收标准 2：选 N 人默认产 N 张结构原样表；用户确认绑定时
  仍可改回 `""` 退化为单份 lead 填充）。`lead_resume` 及其余角色保持
  `mode: ""` 不变；`fill_draft` 仍按 binding 的 mode 执行（Task 5 已实现）。
- 测试：`test_classifier_resume_each_vs_lead_resume` 补断言
  resume_each → `mode=="per_person"`、lead_resume → `""`；既有无
  mode 断言的用例不受影响。
- 命令：`python -m pytest tests/test_bid_classifier.py
  tests/test_bid_resume_clone.py tests/test_api_bid_draft.py -q` →
  `50 passed`；全量 `python -m pytest -q` → `338 passed`（无回归）。
- 提交：`1cd27ae` 商务标：简历表每人一份默认整表克隆
