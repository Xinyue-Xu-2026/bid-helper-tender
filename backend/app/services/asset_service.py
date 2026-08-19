"""资产库 Excel 批量导入。"""
from datetime import date, datetime

from openpyxl import load_workbook

from app.db import Database

COLUMN_MAPS = {
    "credit": {
        "名称": "name", "证书名称": "name",
        "发证机关": "fields.发证机关", "发证日期": "fields.发证日期",
        "有效期至": "expiry_date", "有效期": "expiry_date",
    },
    "person": {
        "姓名": "name",
        "身份证号": "fields.身份证号", "职称": "fields.职称",
        "联系方式": "fields.联系方式", "证书名称": "fields.证书名称",
        "证书有效期至": "expiry_date", "有效期至": "expiry_date", "有效期": "expiry_date",
    },
}


def normalize_date(value) -> str:
    """统一为 YYYY-MM-DD；无法解析返回空串。"""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value).strip().replace("/", "-").replace(".", "-")
    if not s:
        return ""
    try:
        parts = [int(p) for p in s.split("-")]
        if len(parts) == 3:
            return date(parts[0], parts[1], parts[2]).isoformat()
    except (ValueError, IndexError):
        pass
    return ""


def import_assets_excel(db: Database, asset_type: str, file_path: str) -> dict:
    col_map = COLUMN_MAPS[asset_type]
    wb = load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    headers = [str(h).strip() if h else "" for h in next(rows)]
    col_index = {}
    for idx, header in enumerate(headers):
        if header in col_map:
            col_index[idx] = col_map[header]
    if "name" not in col_index.values():
        wb.close()
        return {"imported": 0, "errors": [{"row": 1, "reason": "未找到名称列（首行需包含名称/证书名称/姓名）"}]}

    imported = 0
    errors = []
    for row_num, row in enumerate(rows, start=2):
        record = {"name": "", "expiry_date": "", "fields": {}}
        for idx, target in col_index.items():
            value = row[idx] if idx < len(row) else None
            if target == "name":
                record["name"] = str(value).strip() if value else ""
            elif target == "expiry_date":
                record["expiry_date"] = normalize_date(value)
            else:
                field_name = target.split(".", 1)[1]
                if value is not None and str(value).strip():
                    if isinstance(value, (datetime, date)):
                        record["fields"][field_name] = normalize_date(value)
                    else:
                        record["fields"][field_name] = str(value).strip()
        if not record["name"]:
            if any(v is not None and str(v).strip() for v in row):
                errors.append({"row": row_num, "reason": "名称为空"})
            continue
        db.create_asset(asset_type, record["name"], record["fields"],
                        expiry_date=record["expiry_date"])
        imported += 1
    wb.close()
    return {"imported": imported, "errors": errors}
