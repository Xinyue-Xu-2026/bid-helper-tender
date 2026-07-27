import re
from typing import List


CATEGORY_KEYWORDS = {
    "评分项": ["评分办法", "评分标准", "综合评分", "商务评分", "技术评分"],
    "废标项": ["废标", "无效投标", "否决投标", "投标无效"],
    "资质门槛": ["资格条件", "投标人资格", "资质要求"],
    "格式要求": ["投标文件格式", "投标文件组成", "装订", "目录", "A4", "签字", "盖章", "密封"],
    "时间节点": ["投标截止时间", "开标时间", "有效期", "保证金递交"],
}


def _detect_category(line: str) -> str:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in line for kw in keywords):
            return category
    return "其他"


def _extract_time(line: str) -> List[str]:
    patterns = [
        r"\d{4}年\d{1,2}月\d{1,2}日(?:\d{1,2}时\d{1,2}分)?",
        r"\d{4}-\d{2}-\d{2}",
        r"\d{4}/\d{2}/\d{2}",
    ]
    found = []
    for pat in patterns:
        found.extend(re.findall(pat, line))
    return found


def _extract_amount(line: str) -> List[str]:
    return re.findall(r"人民币[\d,.]+元|[\d,.]+万元", line)


def parse_tender(text: str) -> List[dict]:
    lines = text.splitlines()
    results = []
    current_section = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 识别章节标题
        if re.match(r"^第[一二三四五六七八九十百千]+章|^第\d+章|^\d+\.\d+|^\d+\. ", line):
            current_section = line.split()[0] if line.split() else line[:20]

        category = _detect_category(line)
        if category == "其他":
            continue

        # 提取更具体的内容
        contents = []
        if category == "时间节点":
            times = _extract_time(line)
            contents.extend(times)
        else:
            contents.append(line)

        for content in contents:
            if not content.strip():
                continue
            confidence = "高" if len(content) < 100 else "中"
            results.append({
                "category": category,
                "content": content,
                "source": current_section,
                "confidence": confidence,
                "status": "待响应",
            })

    return results
