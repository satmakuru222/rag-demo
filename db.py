import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.environ.get("SQLITE_DB_PATH", "./rag.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            first_seen TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notebooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS indexed_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notebook_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            source_type TEXT NOT NULL,
            uploaded_by TEXT,
            chunk_count INTEGER,
            indexed_at TEXT NOT NULL,
            UNIQUE(notebook_id, filename),
            FOREIGN KEY(notebook_id) REFERENCES notebooks(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            notebook_id INTEGER,
            question TEXT NOT NULL,
            sources_json TEXT,
            response TEXT,
            ts TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            ts TEXT NOT NULL,
            FOREIGN KEY(query_id) REFERENCES audit_log(id)
        );
    """)
    conn.commit()
    conn.close()

def upsert_user(user_id: str, email: str, name: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users(id, email, name, first_seen) VALUES(?,?,?,?)",
        (user_id, email, name, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

# ── Notebooks ──────────────────────────────────────────────────────────────────

def create_notebook(name: str, owner_id: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO notebooks(name, owner_id, created_at) VALUES(?,?,?)",
        (name, owner_id, datetime.utcnow().isoformat()),
    )
    nb_id = cur.lastrowid
    conn.commit()
    conn.close()
    return nb_id

def get_notebooks(owner_id: str) -> list:
    conn = get_conn()
    rows = conn.execute(
        """SELECT n.id, n.name, n.created_at,
                  COUNT(d.id) as doc_count,
                  COALESCE(SUM(d.chunk_count), 0) as chunk_count
           FROM notebooks n
           LEFT JOIN indexed_docs d ON d.notebook_id = n.id
           WHERE n.owner_id = ?
           GROUP BY n.id ORDER BY n.created_at DESC""",
        (owner_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_notebook(notebook_id: int, owner_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM indexed_docs WHERE notebook_id=?", (notebook_id,))
    conn.execute("DELETE FROM notebooks WHERE id=? AND owner_id=?", (notebook_id, owner_id))
    conn.commit()
    conn.close()

def rename_notebook(notebook_id: int, name: str, owner_id: str):
    conn = get_conn()
    conn.execute("UPDATE notebooks SET name=? WHERE id=? AND owner_id=?", (name, notebook_id, owner_id))
    conn.commit()
    conn.close()

# ── Docs ───────────────────────────────────────────────────────────────────────

def log_indexed_doc(notebook_id: int, filename: str, source_type: str, uploaded_by: str, chunk_count: int):
    conn = get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO indexed_docs(notebook_id, filename, source_type, uploaded_by, chunk_count, indexed_at)
           VALUES(?,?,?,?,?,?)""",
        (notebook_id, filename, source_type, uploaded_by, chunk_count, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

def delete_indexed_doc(notebook_id: int, filename: str):
    conn = get_conn()
    conn.execute("DELETE FROM indexed_docs WHERE notebook_id=? AND filename=?", (notebook_id, filename))
    conn.commit()
    conn.close()

def get_indexed_docs(notebook_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM indexed_docs WHERE notebook_id=? ORDER BY indexed_at DESC",
        (notebook_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Audit / Feedback ───────────────────────────────────────────────────────────

def log_query(user_id: str, notebook_id: int, question: str, sources: list, response: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO audit_log(user_id, notebook_id, question, sources_json, response, ts) VALUES(?,?,?,?,?,?)",
        (user_id, notebook_id, question, json.dumps(sources), response, datetime.utcnow().isoformat()),
    )
    query_id = cur.lastrowid
    conn.commit()
    conn.close()
    return query_id

def log_feedback(query_id: int, user_id: str, rating: int):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO feedback(query_id, user_id, rating, ts) VALUES(?,?,?,?)",
        (query_id, user_id, rating, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

def get_audit_log(limit: int = 50) -> list:
    conn = get_conn()
    rows = conn.execute(
        """SELECT a.id, a.user_id, u.email, a.question, a.response, a.ts, a.notebook_id,
                  n.name as notebook_name,
                  (SELECT rating FROM feedback f WHERE f.query_id=a.id LIMIT 1) as rating
           FROM audit_log a
           LEFT JOIN users u ON u.id=a.user_id
           LEFT JOIN notebooks n ON n.id=a.notebook_id
           ORDER BY a.ts DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
