"""底稿驱动商务标导出：按用户确认的 bindings 填充数据表/简历表/扫描件，
替换残留项目编号/名称/日期，可选目录换 TOC 域，输出填充报告 + 防篡改校验。

bindings JSON schema 权威定义见 bid_table_classifier 模块 docstring；
data 结构见 bid_service.assemble_bid_draft_data
（{"persons":[{name,fields,is_lead,role,sem}],"contracts":[{name,fields,
section,sem}],"lead_perfs_text":str}）。
"""
import os
from copy import deepcopy
from pathlib import Path

from docx import Document

from app.core.bid_template_exporter import (
    _clear_table_images, _insert_image_into_table, _is_toc_paragraph,
    _replace_stale_text, _set_cell_text,
)
from app.core.bid_verify import verify_draft_fill
from app.core.word_exporter import insert_toc_field_at


def _fill_table_semantic(table, columns: dict, sem_rows: list) -> int:
    """语义列填充数据表：保留表头行，deepcopy 首数据行做样式 donor 逐行写入。
    列下标 j → 反向查 columns 得语义键，有则写 sem_row.get(key,"")，无则清 ""；
    横向合并按 _tc 引用去重只写一次。sem_rows 空 → 仅留表头返回 0；
    表只有表头（无数据行）时用表头行做 donor。返回写入行数。"""
    col_to_sem = {col: sem for sem, col in (columns or {}).items()}
    rows = table.rows
    if not rows:
        return 0
    donor_tr = deepcopy(rows[1]._tr if len(rows) >= 2 else rows[0]._tr)
    for r in list(table.rows[1:]):
        r._tr.getparent().remove(r._tr)
    written = 0
    for sem_row in sem_rows or []:
        table._tbl.append(deepcopy(donor_tr))
        new_row = table.rows[-1]
        seen_tcs = []
        for j, cell in enumerate(new_row.cells):
            tc = cell._tc
            if any(tc is t for t in seen_tcs):
                continue
            seen_tcs.append(tc)
            sem = col_to_sem.get(j)
            _set_cell_text(cell, sem_row.get(sem, "") if sem else "")
        written += 1
    return written


def _fill_resume_table(table, label_to_sem: dict, sem: dict,
                       lead_perfs_text: str) -> int:
    """简历键值表填充：逐行逐格，规范化格文本（去首尾空白 + 去尾部
    "："或":"）命中 label_to_sem → 写其右侧首个不同 _tc 的格子（无右格跳过）；
    语义键为 lead_perfs 时写 lead_perfs_text。返回写入格数。"""
    written = 0
    for row in table.rows:
        cells = row.cells
        seen_tcs = []
        for j, cell in enumerate(cells):
            tc = cell._tc
            if any(tc is t for t in seen_tcs):
                continue
            seen_tcs.append(tc)
            label = (cell.text or "").strip().rstrip("：:").strip()
            sem_key = (label_to_sem or {}).get(label)
            if not sem_key:
                continue
            target = None
            for nxt in cells[j + 1:]:
                if nxt._tc is not tc:
                    target = nxt
                    break
            if target is None:
                continue
            value = (lead_perfs_text if sem_key == "lead_perfs"
                     else (sem or {}).get(sem_key, ""))
            _set_cell_text(target, value or "")
            written += 1
    return written


def _fill_image_slots(doc, slot_bindings, persons, report) -> None:
    """逐图片占位表插图。slot_bindings: [(binding, table)]。
    person "lead" → 负责人；"member:N" → 第 N 个非负责人（0 起，
    越界 → report["skipped"] 记 reason="人员不足"）；缺省按负责人。
    图片路径按 label_kind 取 fields：职称证书 → 职称证书扫描件；
    社保 → 社保缴纳证明扫描件；身份证 → 身份证扫描件；
    注册证书 → 按该 person 出现顺序逐次取 fields["证书"][k]["扫描件"]
    （每人独立计数器）。先 _clear_table_images 再 _insert_image_into_table
    （文件不存在内部跳过）。成功/失败记入 report["images"]。"""
    persons = persons or []
    lead = next((p for p in persons if p.get("is_lead")), None)
    members = [p for p in persons if not p.get("is_lead")]
    cert_counters = {}  # id(person) → 已取注册证书数（每人独立）

    for binding, table in slot_bindings:
        who = binding.get("person") or "lead"
        if who == "lead":
            person = lead
        elif who.startswith("member:"):
            try:
                n = int(who.split(":", 1)[1])
            except ValueError:
                n = -1
            person = members[n] if 0 <= n < len(members) else None
        else:
            person = lead
        if person is None:
            report["skipped"].append({
                "table_index": binding.get("table_index"),
                "role": "image_slot", "reason": "人员不足"})
            continue
        fields = person.get("fields") or {}
        kind = binding.get("label_kind") or ""
        if kind == "职称证书":
            image_path = str(fields.get("职称证书扫描件") or "")
        elif kind == "社保":
            image_path = str(fields.get("社保缴纳证明扫描件") or "")
        elif kind == "身份证":
            image_path = str(fields.get("身份证扫描件") or "")
        elif kind == "注册证书":
            certs = [c for c in (fields.get("证书") or [])
                     if isinstance(c, dict)]
            key = id(person)
            k = cert_counters.get(key, 0)
            cert_counters[key] = k + 1
            image_path = (str(certs[k].get("扫描件") or "")
                          if k < len(certs) else "")
        else:
            image_path = ""
        _clear_table_images(table)
        ok = bool(image_path) and Path(image_path).exists()
        if ok:
            _insert_image_into_table(table, image_path)
        report["images"].append({
            "table_index": binding.get("table_index"),
            "person": str(person.get("name") or ""),
            "label_kind": kind, "ok": ok})


def _swap_toc(doc) -> bool:
    """首个连续 toc 样式段落组 → 保留首段位置、删除组内其余段，
    在首段 insert_toc_field_at；无 toc 段 → False。"""
    group = []
    for para in doc.paragraphs:
        if _is_toc_paragraph(para):
            group.append(para)
        elif group:
            break
    if not group:
        return False
    first = group[0]
    for para in group[1:]:
        para._element.getparent().remove(para._element)
    insert_toc_field_at(first)
    return True


def _scope_persons(persons, scope: str) -> list:
    if scope == "lead":
        return [p for p in persons if p.get("is_lead")]
    if scope == "members":
        return [p for p in persons if not p.get("is_lead")]
    return list(persons)


def _scope_contracts(contracts, persons, scope: str) -> list:
    if scope == "lead":
        lead = next((p for p in persons if p.get("is_lead")), None)
        lead_name = str(lead.get("name") or "").strip() if lead else ""
        if not lead_name:
            return []
        return [c for c in contracts
                if str((c.get("fields") or {}).get("项目负责人")
                       or "").strip() == lead_name]
    if scope == "section1":
        return [c for c in contracts if c.get("section") == 1]
    if scope == "section2":
        return [c for c in contracts if c.get("section") == 2]
    return list(contracts)


def fill_draft(draft_path: str, dest_path: str, bindings: dict, data: dict,
               project_no: str = "", project_name: str = "",
               doc_date: str = "") -> dict:
    """按确认的 bindings 填充底稿并另存 dest_path，返回 fill_report。
    dest 与 draft 不得同路径。"""
    if os.path.abspath(str(draft_path)) == os.path.abspath(str(dest_path)):
        raise ValueError("dest 与 draft 不得同路径")
    doc = Document(draft_path)
    # doc.tables：顶层表格、文档顺序（python-docx 按 body 中 w:tbl 顺序收集，
    # 已验证与块遍历一致），与 T5 table_index 同坐标系。
    tables = doc.tables
    data = data or {}
    persons = data.get("persons") or []
    contracts = data.get("contracts") or []
    report = {"filled": [], "images": [], "skipped": [], "verify": None}

    image_slots = []
    bound_indices = set()
    for binding in (bindings or {}).get("tables") or []:
        if not binding.get("confirmed"):
            continue
        role = binding.get("role") or "ignore"
        if role == "ignore":
            continue
        idx = binding.get("table_index")
        if not isinstance(idx, int) or not 0 <= idx < len(tables):
            report["skipped"].append({
                "table_index": idx, "role": role,
                "reason": "表不存在，可能底稿已重新生成"})
            continue
        # 仅 fill 实际会改动的表豁免防篡改校验；quote（手工填写）与未知
        # 角色不改动 → 不豁免，未绑定表同等受校验保护
        if role in ("person_roster", "perf_list", "lead_resume", "image_slot"):
            bound_indices.add(idx)
        table = tables[idx]
        if role == "person_roster":
            picked = _scope_persons(persons, binding.get("person_scope") or "all")
            rows = _fill_table_semantic(table, binding.get("columns") or {},
                                        [p.get("sem") or {} for p in picked])
            report["filled"].append(
                {"table_index": idx, "role": role, "rows": rows})
        elif role == "perf_list":
            picked = _scope_contracts(contracts, persons,
                                      binding.get("perf_scope") or "all")
            rows = _fill_table_semantic(table, binding.get("columns") or {},
                                        [c.get("sem") or {} for c in picked])
            report["filled"].append(
                {"table_index": idx, "role": role, "rows": rows})
        elif role == "lead_resume":
            lead = next((p for p in persons if p.get("is_lead")), None)
            written = 0
            if lead is not None:
                written = _fill_resume_table(
                    table, binding.get("columns") or {},
                    lead.get("sem") or {},
                    str(data.get("lead_perfs_text") or ""))
            report["filled"].append(
                {"table_index": idx, "role": role, "rows": written})
        elif role == "quote":
            report["skipped"].append(
                {"table_index": idx, "role": role, "reason": "报价表需手工填写"})
        elif role == "image_slot":
            image_slots.append((binding, table))

    _fill_image_slots(doc, image_slots, persons, report)
    _replace_stale_text(doc, project_no=project_no,
                        project_name=project_name, doc_date=doc_date)
    swap_toc = bool((bindings or {}).get("swap_toc"))
    if swap_toc:
        _swap_toc(doc)
    doc.save(str(dest_path))
    report["verify"] = verify_draft_fill(
        str(draft_path), str(dest_path),
        bound_table_indices=bound_indices,
        replace_params={"project_no": project_no, "project_name": project_name,
                        "doc_date": doc_date},
        swapped_toc=swap_toc)
    return report
