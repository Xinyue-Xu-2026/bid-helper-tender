# -*- coding: utf-8 -*-
"""仿写规划：让 LLM 输出结构化编辑指令（锚点 + 操作），不产出可执行代码。"""
import json

from app.core.llm_parser import (
    CODING_DEFAULT_MODEL,
    CODING_MODELS,
    DEFAULT_MODEL,
    LLMParseError,
    _friendly_api_error,
    _make_client,
    is_coding_key,
)

SYSTEM_PROMPT = """你是一名投标技术标撰写专家。任务：在【模板章节】基础上做"靶向改写 + 插入项目针对性内容"，生成新项目的同一章投标方案，且【严格保持模板格式不变】。

你必须只输出一个 JSON 对象，结构为 {"ops": [...]}，其中每条 op 只能是以下三种类型之一：

1. insert（在指定段落之后插入一段或多段新内容，每段样式克隆模板对应样式的段落）：
   {"op": "insert", "index": 段落序号, "anchor": "该序号段落的开头几个字",
    "items": [{"style": "样式名", "text": "段落文本"}, {"style": "样式名", "text": "段落文本"}, ...]}
   —— items 按顺序连续插入：第一个紧跟在 anchor 段之后，其后每个紧跟上一段。新增一个小节时，把"标题(Heading 3) + 若干正文(Normal)"放在同一条 insert 的 items 里，顺序为标题在前、正文在后。

2. set_text（改写某个段落的文字，保留其原格式）：
   {"op": "set_text", "index": 段落序号, "anchor": "该序号段落的开头几个字", "text": "改写后的整段文字"}

3. add_row（在表格中含 match 文本的行之后追加一行）：
   {"op": "add_row", "table": 表格序号, "match": "用于定位行的文本", "cells": ["单元格1", "单元格2", ...]}

硬性规则：
1. index 只能取【模板段落锚点】中真实存在的段落序号，绝对不得虚构或猜测序号。
2. anchor 必须是该序号段落文本的真实开头（后端用它校验定位，写错会导致执行失败）。
3. style 只能取【模板段落锚点】中出现过的样式名（如 Normal、Heading 3、Heading 4 等）。
4. 模板中属于公司通用制度/通用性表述的原文一律原样保留，不做润色改写。
5. 项目针对性内容（与招标要求直接呼应的制度、承诺、指标）集中用一条 insert 新增一个小节；少量与招标硬性数字呼应的句子用 set_text 靶向修改或 insert 在对应段落之后。
6. 招标文件中的硬性数字（人数、时限、误差率、违约金比例等）必须原样准确引用。
7. 无法确定、需人工填写的实体信息（具体人名、证书号、公司具体地址等）用【需人工替换：…】标注在文本中。
8. 与招标要求冲突的内容，以招标要求为准并在文中声明。
9. 只输出 JSON，不要输出任何解释性文字、Markdown 代码块或多余内容。"""


def _validate_ops(raw_ops) -> list:
    ops = []
    for item in raw_ops or []:
        if not isinstance(item, dict):
            continue
        op = item.get("op")
        if op == "insert":
            index = item.get("index")
            anchor = str(item.get("anchor") or "")
            items = item.get("items")
            if not (isinstance(index, int) and anchor and isinstance(items, list) and items):
                continue
            norm_items = []
            for it in items:
                if (isinstance(it, dict)
                        and str(it.get("style") or "").strip()
                        and str(it.get("text") or "").strip()):
                    norm_items.append({"style": str(it["style"]).strip(),
                                       "text": str(it["text"]).strip()})
            if not norm_items:
                continue
            ops.append({"op": "insert", "index": index, "anchor": anchor,
                        "items": norm_items})
        elif op == "set_text":
            index = item.get("index")
            text = item.get("text")
            anchor = str(item.get("anchor") or "")
            if not (isinstance(index, int) and isinstance(text, str)
                    and text.strip() and anchor):
                continue
            ops.append({"op": "set_text", "index": index, "anchor": anchor,
                        "text": text.strip()})
        elif op == "add_row":
            table = item.get("table")
            match = str(item.get("match") or "")
            cells = item.get("cells")
            if not (isinstance(table, int) and match
                    and isinstance(cells, list) and cells):
                continue
            ops.append({"op": "add_row", "table": table, "match": match,
                        "cells": [str(c) for c in cells]})
    return ops


def plan_edits(anchor_dump_text: str, requirements_text: str, project_info_text: str,
               api_key: str, model: str = DEFAULT_MODEL, client=None) -> list:
    """调用 LLM 生成编辑指令；任何失败或产出空 ops 抛 LLMParseError。"""
    if not api_key:
        raise LLMParseError("未配置 API Key")
    if is_coding_key(api_key) and model not in CODING_MODELS:
        model = CODING_DEFAULT_MODEL
    client = client or _make_client(api_key)
    user = (f"【项目信息】\n{project_info_text}\n\n"
            f"【招标要求】\n{requirements_text}\n\n"
            f"【模板段落锚点】\n{anchor_dump_text[:12000]}")
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 16384 if is_coding_key(api_key) else 8192,
    }
    if not is_coding_key(api_key):
        kwargs["temperature"] = 0.2
    try:
        completion = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise LLMParseError(_friendly_api_error(exc)) from exc
    if not completion.choices:
        raise LLMParseError("API 返回缺少 choices")
    choice = completion.choices[0]
    if choice.finish_reason == "length":
        raise LLMParseError("输出被截断（finish_reason=length）")
    try:
        data = json.loads(choice.message.content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMParseError(f"返回内容不是合法 JSON：{exc}") from exc

    ops = _validate_ops(data.get("ops") if isinstance(data, dict) else [])
    if not ops:
        raise LLMParseError("LLM 未产出有效编辑指令")
    return ops
