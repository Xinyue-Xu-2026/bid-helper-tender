from pathlib import Path

APP_ROOT = Path("D:/00工作+学习/宏信天德/投标助手/投标APP")
DATA_DIR = APP_ROOT / "data"
IMPORTS_DIR = APP_ROOT / "imports"
PROJECTS_DIR = APP_ROOT / "projects"
DB_PATH = DATA_DIR / "app.db"


def ensure_dirs() -> None:
    for d in (DATA_DIR, IMPORTS_DIR, PROJECTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
