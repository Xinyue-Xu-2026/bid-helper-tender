import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import List, Optional

from app import config

ASSET_TYPES = ("info", "credit", "person", "material")


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(config.DB_PATH)

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_schema(self):
        config.ensure_dirs()
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    client TEXT DEFAULT '',
                    bid_date TEXT DEFAULT '',
                    project_type TEXT DEFAULT '其他',
                    notes TEXT DEFAULT '',
                    tender_file_path TEXT DEFAULT '',
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
                    source TEXT DEFAULT '',
                    confidence TEXT DEFAULT '中',
                    status TEXT DEFAULT '待响应',
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    fields TEXT DEFAULT '{}',
                    file_path TEXT DEFAULT '',
                    expiry_date TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compliance_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    requirement_id INTEGER NOT NULL,
                    checked INTEGER DEFAULT 0,
                    checked_at TEXT,
                    ai_result TEXT,
                    ai_confidence TEXT,
                    UNIQUE (project_id, requirement_id),
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (requirement_id) REFERENCES requirements(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    file_path TEXT DEFAULT '',
                    mode TEXT DEFAULT 'example',
                    style_profile TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    file_path TEXT DEFAULT '',
                    file_type TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    parent_id INTEGER DEFAULT 0,
                    title TEXT NOT NULL,
                    level INTEGER DEFAULT 1,
                    content TEXT DEFAULT '',
                    gen_status TEXT DEFAULT '未生成',
                    sort_order INTEGER DEFAULT 0,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)

    # ---------- 项目 ----------
    def create_project(self, name: str, client: str = "", bid_date: str = "",
                       project_type: str = "其他", notes: str = "") -> int:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO projects (name, client, bid_date, project_type, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, client, bid_date, project_type, notes, now, now))
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
        allowed = {"name", "client", "bid_date", "project_type", "notes", "tender_file_path"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE projects SET {set_clause}, updated_at = ? WHERE id = ?",
                list(fields.values()) + [datetime.now().isoformat(), project_id])

    def delete_project(self, project_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    # ---------- 要求 ----------
    def create_requirement(self, project_id: int, category: str, content: str,
                           source: str = "", confidence: str = "中",
                           status: str = "待响应") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO requirements (project_id, category, content, source, confidence, status) VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, category, content, source, confidence, status))
            return cur.lastrowid

    def get_requirements(self, project_id: int, category: str = None,
                         status: str = None, q: str = None) -> List[dict]:
        sql = "SELECT * FROM requirements WHERE project_id = ?"
        params: list = [project_id]
        if category:
            sql += " AND category = ?"
            params.append(category)
        if status:
            sql += " AND status = ?"
            params.append(status)
        if q:
            sql += " AND content LIKE ?"
            params.append(f"%{q}%")
        sql += " ORDER BY id"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def get_requirement(self, requirement_id: int) -> Optional[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM requirements WHERE id = ?", (requirement_id,)).fetchone()
            return dict(row) if row else None

    def update_requirement(self, requirement_id: int, **kwargs):
        allowed = {"category", "content", "source", "confidence", "status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        with self._connect() as conn:
            conn.execute(f"UPDATE requirements SET {set_clause} WHERE id = ?",
                         list(fields.values()) + [requirement_id])

    def delete_requirement(self, requirement_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM requirements WHERE id = ?", (requirement_id,))

    def delete_requirements_by_project(self, project_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM requirements WHERE project_id = ?", (project_id,))

    def replace_requirements(self, project_id: int, reqs: list):
        """在单个事务内先删后插项目要求（避免半途失败留下空清单）。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM requirements WHERE project_id = ?", (project_id,))
            for req in reqs:
                conn.execute(
                    "INSERT INTO requirements (project_id, category, content, source, confidence, status) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (project_id, req["category"], req["content"], req["source"],
                     req["confidence"], req["status"]))

    # ---------- 资产 ----------
    def create_asset(self, type: str, name: str, fields: dict = None,
                     file_path: str = "", expiry_date: str = "") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO assets (type, name, fields, file_path, expiry_date) VALUES (?, ?, ?, ?, ?)",
                (type, name, json.dumps(fields or {}, ensure_ascii=False), file_path, expiry_date))
            return cur.lastrowid

    @staticmethod
    def _asset_row(row) -> dict:
        d = dict(row)
        try:
            d["fields"] = json.loads(d.get("fields") or "{}")
        except json.JSONDecodeError:
            d["fields"] = {}
        return d

    def get_assets(self, type: str = None) -> List[dict]:
        sql = "SELECT * FROM assets"
        params: list = []
        if type:
            sql += " WHERE type = ?"
            params.append(type)
        sql += " ORDER BY id DESC"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return [self._asset_row(r) for r in conn.execute(sql, params).fetchall()]

    def get_asset(self, asset_id: int) -> Optional[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
            return self._asset_row(row) if row else None

    def update_asset(self, asset_id: int, **kwargs):
        allowed = {"name", "fields", "file_path", "expiry_date"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if "fields" in fields and isinstance(fields["fields"], dict):
            fields["fields"] = json.dumps(fields["fields"], ensure_ascii=False)
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        with self._connect() as conn:
            conn.execute(f"UPDATE assets SET {set_clause} WHERE id = ?",
                         list(fields.values()) + [asset_id])

    def delete_asset(self, asset_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))

    def get_expiring_assets(self, days: int = 30) -> List[dict]:
        today = date.today()
        limit = today + timedelta(days=days)
        results = []
        for a in self.get_assets():
            raw = (a.get("expiry_date") or "").strip()
            if not raw:
                continue
            try:
                d = date.fromisoformat(raw)
            except ValueError:
                continue
            if today <= d <= limit:
                a["days_left"] = (d - today).days
                results.append(a)
        return sorted(results, key=lambda x: x["days_left"])

    # ---------- 废标核对 ----------
    def set_check(self, project_id: int, requirement_id: int, checked: bool):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO compliance_checks (project_id, requirement_id, checked, checked_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (project_id, requirement_id)
                DO UPDATE SET checked = excluded.checked, checked_at = excluded.checked_at
            """, (project_id, requirement_id, 1 if checked else 0, datetime.now().isoformat()))

    def get_checks(self, project_id: int) -> dict:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM compliance_checks WHERE project_id = ?", (project_id,)).fetchall()
            return {r["requirement_id"]: dict(r) for r in rows}

    # ---------- 模板 ----------
    def create_template(self, name: str, file_path: str, mode: str = "example") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO templates (name, file_path, mode) VALUES (?, ?, ?)",
                (name, file_path, mode))
            return cur.lastrowid

    def get_templates(self) -> List[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM templates ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]

    def get_template(self, template_id: int) -> Optional[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
            return dict(row) if row else None

    def update_template(self, template_id: int, **kwargs):
        allowed = {"name", "file_path", "mode", "style_profile"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        with self._connect() as conn:
            conn.execute(f"UPDATE templates SET {set_clause} WHERE id = ?",
                         list(fields.values()) + [template_id])

    def delete_template(self, template_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))

    # ---------- 项目资料 ----------
    def create_material(self, project_id: int, file_path: str, file_type: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO materials (project_id, file_path, file_type) VALUES (?, ?, ?)",
                (project_id, file_path, file_type))
            return cur.lastrowid

    def get_materials(self, project_id: int) -> List[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM materials WHERE project_id = ? ORDER BY id DESC",
                (project_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_material(self, material_id: int) -> Optional[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
            return dict(row) if row else None

    def delete_material(self, material_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM materials WHERE id = ?", (material_id,))

    # ---------- 章节 ----------
    def create_section(self, project_id: int, parent_id: int, title: str,
                       level: int, sort_order: int) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO sections (project_id, parent_id, title, level, sort_order) VALUES (?, ?, ?, ?, ?)",
                (project_id, parent_id, title, level, sort_order))
            return cur.lastrowid

    def get_sections(self, project_id: int) -> List[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM sections WHERE project_id = ? ORDER BY sort_order, id",
                (project_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_section(self, section_id: int) -> Optional[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM sections WHERE id = ?", (section_id,)).fetchone()
            return dict(row) if row else None

    def update_section(self, section_id: int, **kwargs):
        allowed = {"parent_id", "title", "level", "content", "gen_status", "sort_order"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        with self._connect() as conn:
            conn.execute(f"UPDATE sections SET {set_clause} WHERE id = ?",
                         list(fields.values()) + [section_id])

    def delete_section(self, section_id: int):
        """删除章节及其全部后代（parent_id 无自引用外键，递归收集后删除）。"""
        def collect(conn, sid):
            ids = [sid]
            for row in conn.execute(
                    "SELECT id FROM sections WHERE parent_id = ?", (sid,)).fetchall():
                ids.extend(collect(conn, row[0]))
            return ids
        with self._connect() as conn:
            ids = collect(conn, section_id)
            conn.execute(
                f"DELETE FROM sections WHERE id IN ({','.join('?' * len(ids))})", ids)

    def delete_sections_by_project(self, project_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM sections WHERE project_id = ?", (project_id,))

    def get_sections_tree(self, project_id: int) -> List[dict]:
        """嵌套章节树（children 键），同级按 sort_order 排序。"""
        flat = self.get_sections(project_id)
        nodes = {s["id"]: {**s, "children": []} for s in flat}
        roots = []
        for s in flat:
            node = nodes[s["id"]]
            parent = nodes.get(s["parent_id"])
            (parent["children"] if parent else roots).append(node)
        return roots

    def get_sections_flat(self, project_id: int) -> List[dict]:
        """先序遍历的扁平章节列表（写作/导出顺序，无 children 键）。"""
        result = []

        def walk(nodes):
            for n in nodes:
                result.append({k: v for k, v in n.items() if k != "children"})
                walk(n["children"])
        walk(self.get_sections_tree(project_id))
        return result
