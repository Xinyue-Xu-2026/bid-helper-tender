from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent.parent  # 投标Web平台/
DATA_DIR = APP_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
TEMPLATES_DIR = DATA_DIR / "templates"
MATERIALS_DIR = DATA_DIR / "materials"
FILES_DIR = DATA_DIR / "files"
DB_PATH = DATA_DIR / "app.db"
BID_TEMPLATE_PATH = DATA_DIR / "商务标模板.docx"


def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOADS_DIR, TEMPLATES_DIR, MATERIALS_DIR, FILES_DIR):
        d.mkdir(parents=True, exist_ok=True)
