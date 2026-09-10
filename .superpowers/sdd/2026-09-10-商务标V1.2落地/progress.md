# SDD ledger — plan: D:\00工作+学习\宏信天德\投标助手\投标Web平台\docs\plans\2026-09-10-商务标V1.2落地.md

Spec: D:\00工作+学习\宏信天德\投标助手\需求分析\商务标导出细节优化-需求分析V1.2.docx
Branch: phase2 (当前分支, base a9e7865)

## Pre-flight scan (task × shared-file / interface)

| 检查对 | 共享产物 | 结论 |
|---|---|---|
| T1 ↔ T2 | `bid_template_exporter.compute_text_subs/_replace_stale_text` 签名 | T2 消费 T1 的 section 参数；串行，无冲突 |
| T1 ↔ T3 | 同文件（迭代器 vs 图片工具） | 串行，无冲突 |
| T2 ↔ T3 | `bid_draft_exporter.fill_draft` / `_insert_image_into_table` | 串行 |
| T3 ↔ T5 | `bid_draft_exporter._append_images`/report images 结构 | T3 先改，T5 复用；无冲突 |
| T4 ↔ T5 | `bid_table_classifier` 角色/列语义、`_BINDING_KEYS` | 串行，T4 先 |
| T5 ↔ T6 | 文件不同（T6 只动 page_setup） | 可先后，`fill_draft` 只被 T5 改 |
| T5 ↔ T7 | 同文件（resume 分支/classifier） | 串行 |
| T8 ↔ T9 | `frontend/src/api/index.js` | 串行或批量 |
| T1 ↔ verify 全局约束 | "fill/verify 共用规则与迭代器" | T1 已内建对称；合规 |
| T3 ↔ T5 report images 键 | `images[].reason` | T3 加，T8 渲染；一致 |
| T5 ↔ T8 report filled.cloned | binding `mode`、`filled[].cloned` | 契约一致 |

计划自带、可能被 reviewer 视为缺陷的项：
- T1 测试用裸 XML `addnext` 构造文本框（计划明文要求）——Ruling: 允许；若 implementer 能给出更稳的构造方式更好，但行为断言（文本框被遍历一次）是硬指标。
- T3 修改 `_insert_image_into_table` 签名（计划明文）——Ruling: 保留旧无 report 调用兼容，非破坏性。

Rulings: 无跨任务冲突需裁决。

## 进度

Task 1: implemented 35ef158 (292 passed); review ❌ — Finding1 Important(文本框 AlternateContent 命中 Choice+Fallback 双份→段落重复) + Finding2 Important(组合规则括号风格) + minor(docstring).
Task 1: Ruling on Finding2 — 组合输出保留底稿匹配到的括号风格（半角→半角，全角→全角），而非强制全角；理由：brief 测试与实现要点自相矛盾，以可执行测试+底稿实际(里下河为半角)为准。代价：若招标明确要求全角组合，需微调（低）。
Task 1: fix round 1/5 dispatched (Fallback 去重+括号风格保留+docstring).
Task 1: fix round 1/5 (3 addressed, 0 open; commits 35ef158..5e2e7ad) — Fallback 去重含新测试、组合括号风格保留(全/半角)、docstring 补齐.
Task 1: complete (commits a9e7865..5e2e7ad, review clean; 294 passed)
Task 1: minor (deferred): section_combo 规则 value 字段仍硬编码半角，scan_placeholders 报告 value 在全角底稿上与实际输出不符（仅展示层）.
Task 2: implemented 8af9747 (297 passed); review spec ✅ quality Approved, 无 Critical/Important.
Task 2: complete (commits 5e2e7ad..8af9747, review clean)
Task 2: minor (deferred): section 持久化在 fill 前写入(导出失败仍落库); 清空 section 无法经导出端点回写; test client 参数未用(无害).
Task 3: implemented 30d46f5 (302 passed); review spec ✅ quality Approved, 无 Critical/Important.
Task 3: complete (commits 8af9747..30d46f5, review clean)
Task 3: minor (deferred): 空路径与文件丢失同报"图片文件不存在"(噪音); cell 宽对多列求和(现役均1列); 降采样句柄/重复打开; 旧模板插图宽度随自适应; docstring 残留.
Task 4: implemented fbf6754 (308 passed); review spec ✅ quality Approved, 无 Critical/Important.
Task 4: complete (commits 30d46f5..fbf6754, review clean)
Task 4: minor (deferred): "无数据语义"仅取"含数字"信号(brief 提及金额/姓名未实现); 新测试文件尾无换行; role 端到端测试置于 classifier 测试文件.
Task 5: implemented 42d325a (315 passed); review spec ✅ quality Changes needed — Finding1 Important(克隆表间无分隔段→Word 合并为一张) + minor(空段过滤假阴性面/克隆内容不受校验[设计接受]/位移映射无测试/分类器 col0 全行标记[设计接受]).
Task 5: fix round 1/5 dispatched (表间分隔修复 + 相邻表/位移映射回归测试 + docstring).
Task 5: fix round 1/5 (4 addressed, 0 open; commits 42d325a..ccdb7d6) — 分隔段置于表间(修复 Word 合并)、新增无相邻表/哨兵位移测试、docstring 披露.
Task 5: complete (commits fbf6754..ccdb7d6, review clean; 317 passed)
Task 5: parked/accepted: 空段过滤致纯图片段不入段落比对(已在 docstring 披露, 图片改动由表格/文本框维度兜底); 克隆表内容不受校验(纯生成内容, brief 设计).
Task 6: implemented 05e7fb9 (324 passed); review spec ✅ quality Approved, 无 Critical/Important.
Task 6: complete (commits ccdb7d6..05e7fb9, review clean)
Task 6: minor (deferred): 补 jc 追加到 pPr 末尾可能违 CT_PPr 顺序(仅"缺 jc 且有 rPr"命中, 参考页脚自带 center 不触发); 静态目录正则 \s 计分隔符(双空格+尾数字)误判风险; 降级 sections=1 名义值; 重复执行非幂等(既有同构); PAGE 子串连带 NUMPAGES(过度覆盖无害).
Task 7: implemented 9ce8d35 (330 passed); review spec ✅ quality Approved, 无 Critical/Important.
Task 7: complete (commits 05e7fb9..9ce8d35, review clean)
Task 7: minor (deferred): 中小表密集合并(≥3处)会切 mesh(行为扩展非回归); _is_grid_resume 列数口径与 mesh 在病态表可能不一致; 大网格识别仍只看 col0 标签(召回上限).
Ruling (plan gap): 计划 Task 8/9 假设存在占位符预览端点与同义词 API，但 Task 1 只实现了 core scan_placeholders/同义词存取、未建路由端点。新增后端前置小任务 Task 8a（占位符预览 + 同义词 API）交付给 fix-1，随后 Task 8/9 前端交给 @designer。代价：若端点契约与前端预期不符，前端需微调（低）。
Task 8a: implemented aaf8602 (334 passed); review spec ✅ quality Approved, 无 Critical/Important.
Task 8a: complete (commits 9ce8d35..aaf8602, review clean)
Task 8a: minor (deferred): preview 字段 str 非 Optional(null→422); 每次预览整载底稿; PUT 同义词全量覆盖语义.
Ruling (real gap): review 发现用户配置的同义词只影响预览端点，导出/校验路径仍传 synonyms=None→默认库，违反 V1.2 4.5（同义词库须影响替换）。新增 Task 9a：把 settings_store.get_placeholder_synonyms() 接入 fill_draft 与 verify replace_params。代价：不接则同义词库对导出无效（本就在修）。
Task 9a: implemented 1db1d30 (336 passed); review spec ✅ quality Approved, 无 Critical/Important.
Task 9a: complete (commits aaf8602..1db1d30, review clean)
Task 9a: minor (deferred/known deviation): 旧模板回退路径 build_bid_docx_from_template 本就无 label 填充(只换编号/名/日期)，同义词对其无意义，非真实缺陷.
Ruling (plan gap): 计划 Task 8 前端消费 report.placeholders，但后端 fill_draft 从未加该键。新增 Task 8b（导出报告纳入占位符清单）交付 fix-1。代价：无则报告对话框无占位符数据（低）。
Task 8b: implemented 55e83e9 (338 passed); review spec ✅ quality Approved, 无 Critical/Important.
Task 8b: complete (commits 1db1d30..55e83e9, review clean).
Task 8 (前端): implemented c42f22e (npm run build 绿); review spec ✅ quality Approved, 无 Critical/Important.
Task 8: complete (commits 55e83e9..c42f22e, review clean)
Task 8: minor (deferred→本次修): too_long 提示仅渲染在失败分支(成功但过高场景不显示, 违 V1.2 6.2) → 改两分支都渲染; header_rows 提交无上限兜底 → min(4,..).
Ruling: 为满足验收标准(2)"选 N 人导出 N 张结构原样简历表"，classifier 对 resume_each 建议默认 mode="per_person"（用户可关）。理由：resume_each 定义即"简历表每人一份"，默认开才开箱即用。代价：若某 resume_each 表实为单份样表会被默认克隆，用户可关闭并重导（低）。
Task 8 跟进(1cd27ae 后端 resume_each 默认 per_person; 3afed8d Task9 同义词UI; 0e71ea9 too_long/header_rows 修复): 合并评审 spec 全 ✅ quality Approved, 无 Critical/Important; npm build 绿.
Task 8/9: complete.
Task 9: minor (deferred): 默认同义词行删除后静默复活(GET 合并视图 + PUT 覆盖层，无法停用默认别名); 合并视图回存使默认值冻结为覆盖项.
Task 5: minor (deferred): 分类器建议 resume_each 默认开克隆→全选确认即 N 张表(目标行为, 复选框可关).
Task 10 终审(a9e7865..1cd27ae, 10 commits): Ready with fixes — Finding1 Important(文本框校验×表格填充交叉误报: _set_cell_text 删除含 drawing/pict 的段落 + verify _textbox_texts 未豁免表内文本框/克隆翻倍 → verify 误报). 其余 Minor 全部 ship.
Task 10: 终审 fix wave dispatched (1 finding): _set_cell_text 保留含 w:drawing/w:pict 的段落 + verify 文本框比对仅限表外(body-level) + 回归测试.
Task 10: 终审修复由 controller 直接实现（fix-1 两次、fix-2 一次派发均空返回/session error；ora-1 复评空返回、ora-2 session error）。commits 14c6c23(修复) + 14eea69(计划文档)。
Task 10: 证据 — 聚焦 64 passed；全量 `python -m pytest -q` → 342 passed（338 基线 + 4 新回归：_set_cell_text 保留 drawing 段落/首段 drawing run、_textbox_texts 排除表内文本框、单元格含文本框的 fill+verify 端到端 ok）。npm run build 绿。
Task 10: 限制 — 最终小修的独立复评未能完成（评审会话连续 session error）；判定基于 controller 直接运行的全量测试证据 + 4 个精确复现缺陷的回归用例。

