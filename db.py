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

        CREATE TABLE IF NOT EXISTS indexed_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            source_type TEXT NOT NULL,
            uploaded_by TEXT,
            chunk_count INTEGER,
            indexed_at TEXT NOT NULL,
            UNIQUE(filename, source_type)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
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

def log_query(user_id: str, question: str, sources: list, response: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO audit_log(user_id, question, sources_json, response, ts) VALUES(?,?,?,?,?)",
        (user_id, question, json.dumps(sources), response, datetime.utcnow().isoformat()),
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

def log_indexed_doc(filename: str, source_type: str, uploaded_by: str, chunk_count: int):
    conn = get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO indexed_docs(filename, source_type, uploaded_by, chunk_count, indexed_at)
           VALUES(?,?,?,?,?)""",
        (filename, source_type, uploaded_by, chunk_count, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

def get_audit_log(limit: int = 50) -> list:
    conn = get_conn()
    rows = conn.execute(
        """SELECT a.id, a.user_id, u.email, a.question, a.response, a.ts,
                  (SELECT rating FROM feedback f WHERE f.query_id=a.id LIMIT 1) as rating
           FROM audit_log a LEFT JOIN users u ON u.id=a.user_id
           ORDER BY a.ts DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_indexed_docs() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM indexed_docs ORDER BY indexed_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
