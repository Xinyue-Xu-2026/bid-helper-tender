"""模板策略抽象：决定如何把模板信息注入生成 prompt。

v1 仅 ExampleReferenceStrategy（范例参考）；预留 SkeletonFillStrategy（骨架填充）等扩展。
"""
from pathlib import Path

from app.core.extractor import extract_text


class TemplateStrategy:
    """模板策略接口：输入模板记录，输出注入 prompt 的文本（空串表示无注入）。"""

    def build_prompt(self, template: dict) -> str:
        raise NotImplementedError


class ExampleReferenceStrategy(TemplateStrategy):
    """范例参考策略：优先注入预生成的风格画像；无画像时退化为模板原文节选。"""

    MAX_EXCERPT = 3000

    def build_prompt(self, template: dict) -> str:
        if not template:
            return ""
        profile = (template.get("style_profile") or "").strip()
        if profile:
            return f"【模板风格画像】\n{profile}"
        path = template.get("file_path") or ""
        if path and Path(path).exists():
            excerpt = extract_text(path)[: self.MAX_EXCERPT]
            if excerpt.strip():
                return f"【模板原文节选（供参考写作风格）】\n{excerpt}"
        return ""
