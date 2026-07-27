import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from bidhelper import config


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(config.DB_PATH)

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def init_schema(self):
        config.ensure_dirs()
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    client TEXT,
                    bid_date TEXT,
                    project_type TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS requirements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT,
                    confidence TEXT,
                    status TEXT DEFAULT '待响应',
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)

    def create_project(self, name: str, client: str = "", bid_date: str = "",
                       project_type: str = "其他", notes: str = "") -> int:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO projects (name, client, bid_date, project_type, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, client, bid_date, project_type, notes, now, now)
            )
            return cur.lastrowid

    def get_projects(self) -> List[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
            return [dict(r) for r in rows]

    def get_project(self, project_id: int) -> Optional[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            return dict(row) if row else None

    def update_project(self, project_id: int, **kwargs):
        allowed = {"name", "client", "bid_date", "project_type", "notes"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [project_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE projects SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )

    def delete_project(self, project_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    def create_requirement(self, project_id: int, category: str, content: str,
                           source: str = "", confidence: str = "中",
                           status: str = "待响应") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO requirements (project_id, category, content, source, confidence, status) VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, category, content, source, confidence, status)
            )
            return cur.lastrowid

    def get_requirements(self, project_id: int) -> List[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM requirements WHERE project_id = ? ORDER BY id",
                (project_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def update_requirement(self, requirement_id: int, **kwargs):
        allowed = {"category", "content", "source", "confidence", "status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [requirement_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE requirements SET {set_clause} WHERE id = ?",
                values
            )

    def delete_requirement(self, requirement_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM requirements WHERE id = ?", (requirement_id,))
