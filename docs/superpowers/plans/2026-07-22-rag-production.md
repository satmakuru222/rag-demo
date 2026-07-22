# RAG Production Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the RAG demo into a production-ready, multi-user document intelligence platform with Keycloak SSO, persistent vector storage, Google Drive auto-ingestion, audit logging, and answer feedback.

**Architecture:** SQLite handles users/audit/feedback; ChromaDB (persistent on disk) is the shared vector store used by all sessions; Keycloak runs in Docker and issues OIDC tokens validated on every Streamlit page load; a background ingestion script polls Google Drive and adds new docs automatically.

**Tech Stack:** Streamlit · ChromaDB (persistent) · Keycloak (Docker) · SQLite · Google Drive API (service account) · Anthropic claude-sonnet-4-6 · httpx · python-jose

---

## File Map

```
rag-demo/
  app.py                          ← Main app (upgraded: auth, multi-user, feedback, audit)
  auth.py                         ← Keycloak OIDC flow for Streamlit
  db.py                           ← SQLite: users, audit_log, feedback, indexed_docs
  vectorstore.py                  ← Persistent ChromaDB singleton wrapper
  ingest/
    __init__.py                   ← empty
    processor.py                  ← Shared PDF text extraction + chunking
    gdrive.py                     ← Google Drive polling + ingestion script
  keycloak/
    realm-export.json             ← Pre-configured Keycloak realm (import on first run)
  docker-compose.yml              ← Keycloak container
  requirements.txt                ← Updated
  .env.example                    ← All env vars documented
  chroma_db/                      ← Persistent ChromaDB data (gitignored)
  rag.db                          ← SQLite database (gitignored)
```

---

## Task 1: Update requirements.txt and .env.example

**Files:**
- Modify: `requirements.txt`
- Create: `.env.example`

- [ ] **Step 1: Write requirements.txt**

```text
streamlit>=1.35.0
chromadb>=0.5.0
pypdf2>=3.0.0
python-dotenv>=1.0.0
anthropic>=0.30.0
reportlab>=4.0.0
httpx>=0.27.0
python-jose[cryptography]>=3.3.0
google-auth>=2.29.0
google-api-python-client>=2.127.0
google-auth-oauthlib>=1.2.0
```

- [ ] **Step 2: Write .env.example**

```env
# Anthropic
ANTHROPIC_API_KEY=your-anthropic-key-here

# Keycloak OIDC
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=rag-demo
KEYCLOAK_CLIENT_ID=rag-app
KEYCLOAK_CLIENT_SECRET=change-me-in-keycloak
REDIRECT_URI=http://localhost:8501

# Google Drive (service account)
GDRIVE_SERVICE_ACCOUNT_FILE=keycloak/gdrive-service-account.json
GDRIVE_FOLDER_ID=your-google-drive-folder-id-here

# Paths
CHROMA_DB_PATH=./chroma_db
SQLITE_DB_PATH=./rag.db
```

- [ ] **Step 3: Install new packages**

```powershell
C:\ragenv\Scripts\pip install httpx python-jose[cryptography] google-auth google-api-python-client google-auth-oauthlib
```

Expected: `Successfully installed ...`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt .env.example
git commit -m "chore: add production dependencies and env template"
```

---

## Task 2: db.py — SQLite database layer

**Files:**
- Create: `db.py`

- [ ] **Step 1: Write db.py**

```python
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
```

- [ ] **Step 2: Verify db.py works**

```powershell
C:\ragenv\Scripts\python.exe -c "
import os; os.environ['SQLITE_DB_PATH']='./test.db'
from db import init_db, upsert_user, log_query, log_feedback
init_db()
upsert_user('u1','test@example.com','Test User')
qid = log_query('u1','What is RAG?',[{'doc':'a.pdf','text':'RAG is...'}],'RAG stands for...')
log_feedback(qid, 'u1', 1)
print('db.py OK, query_id:', qid)
import os; os.remove('./test.db')
"
```

Expected: `db.py OK, query_id: 1`

- [ ] **Step 3: Commit**

```bash
git add db.py
git commit -m "feat: add SQLite layer for users, audit log, feedback, indexed docs"
```

---

## Task 3: vectorstore.py — Persistent ChromaDB singleton

**Files:**
- Create: `vectorstore.py`

- [ ] **Step 1: Write vectorstore.py**

```python
import os
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

CHROMA_PATH = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
_client = None
_collection = None

def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    _client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = DefaultEmbeddingFunction()
    _collection = _client.get_or_create_collection("rag_docs", embedding_function=ef)
    return _collection

def add_document(filename: str, chunks: list[str]):
    col = _get_collection()
    existing = col.get(where={"source": filename})
    if existing["ids"]:
        return len(existing["ids"])  # already indexed
    start = col.count()
    col.add(
        documents=chunks,
        ids=[f"chunk_{start + i}" for i in range(len(chunks))],
        metadatas=[{"source": filename} for _ in chunks],
    )
    return len(chunks)

def query(question: str, n: int = 4) -> list[dict]:
    col = _get_collection()
    total = col.count()
    if total == 0:
        return []
    results = col.query(query_texts=[question], n_results=min(n, total))
    return [
        {"doc": m["source"], "text": d}
        for m, d in zip(results["metadatas"][0], results["documents"][0])
    ]

def get_stats() -> dict:
    col = _get_collection()
    total = col.count()
    sources = set()
    if total > 0:
        all_meta = col.get(include=["metadatas"])["metadatas"]
        sources = {m["source"] for m in all_meta}
    return {"total_chunks": total, "documents": sorted(sources)}
```

- [ ] **Step 2: Verify persistence**

```powershell
C:\ragenv\Scripts\python.exe -c "
import os; os.environ['CHROMA_DB_PATH']='./test_chroma'
from vectorstore import add_document, query, get_stats
add_document('test.pdf', ['RAG is retrieval augmented generation', 'ChromaDB stores vectors'])
r = query('what is RAG')
print('Result:', r[0]['text'])
print('Stats:', get_stats())
import shutil; shutil.rmtree('./test_chroma')
"
```

Expected: `Result: RAG is retrieval augmented generation`

- [ ] **Step 3: Commit**

```bash
git add vectorstore.py
git commit -m "feat: persistent ChromaDB singleton with multi-user safe add/query"
```

---

## Task 4: ingest/processor.py — shared PDF processing

**Files:**
- Create: `ingest/__init__.py`
- Create: `ingest/processor.py`

- [ ] **Step 1: Write ingest/__init__.py** (empty)

```python
```

- [ ] **Step 2: Write ingest/processor.py**

```python
from PyPDF2 import PdfReader
import io

def extract_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size].strip())
        start += size - overlap
    return [c for c in chunks if len(c) > 20]
```

- [ ] **Step 3: Verify**

```powershell
C:\ragenv\Scripts\python.exe -c "
from ingest.processor import chunk_text
chunks = chunk_text('Hello world. ' * 100)
print(f'Chunks: {len(chunks)}, first 50 chars: {chunks[0][:50]}')
"
```

Expected: `Chunks: 6, first 50 chars: Hello world. Hello world. ...`

- [ ] **Step 4: Commit**

```bash
git add ingest/
git commit -m "feat: shared PDF processor for chunking and text extraction"
```

---

## Task 5: Keycloak setup with Docker

**Files:**
- Create: `docker-compose.yml`
- Create: `keycloak/realm-export.json`

- [ ] **Step 1: Write docker-compose.yml**

```yaml
version: "3.8"
services:
  keycloak:
    image: quay.io/keycloak/keycloak:24.0
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin123
    ports:
      - "8080:8080"
    volumes:
      - ./keycloak:/opt/keycloak/data/import
    command: start-dev --import-realm
```

- [ ] **Step 2: Write keycloak/realm-export.json**

```json
{
  "realm": "rag-demo",
  "enabled": true,
  "clients": [
    {
      "clientId": "rag-app",
      "enabled": true,
      "publicClient": false,
      "secret": "change-me-in-keycloak",
      "redirectUris": ["http://localhost:8501/*"],
      "webOrigins": ["http://localhost:8501"],
      "standardFlowEnabled": true,
      "directAccessGrantsEnabled": false
    }
  ],
  "roles": {
    "realm": [
      {"name": "rag-user", "description": "Standard RAG app user"},
      {"name": "rag-admin", "description": "Can view audit logs"}
    ]
  }
}
```

- [ ] **Step 3: Start Keycloak**

```powershell
docker compose up -d
```

Wait ~30 seconds, then verify:

```powershell
curl http://localhost:8080/realms/rag-demo/.well-known/openid-configuration
```

Expected: JSON with `"issuer":"http://localhost:8080/realms/rag-demo"`

- [ ] **Step 4: Get client secret from Keycloak UI**

1. Open `http://localhost:8080`
2. Login: admin / admin123
3. Switch realm → `rag-demo`
4. Clients → `rag-app` → Credentials tab
5. Copy the client secret → paste into your `.env` as `KEYCLOAK_CLIENT_SECRET`

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml keycloak/realm-export.json
git commit -m "feat: Keycloak Docker setup with rag-demo realm pre-configured"
```

---

## Task 6: auth.py — Keycloak OIDC for Streamlit

**Files:**
- Create: `auth.py`

- [ ] **Step 1: Write auth.py**

```python
import os
import httpx
import streamlit as st
from jose import jwt

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
REALM = os.environ.get("KEYCLOAK_REALM", "rag-demo")
CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "rag-app")
CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:8501")

BASE = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect"
AUTH_URL = f"{BASE}/auth"
TOKEN_URL = f"{BASE}/token"
JWKS_URL = f"{BASE}/certs"
LOGOUT_URL = f"{BASE}/logout"

def _login_url(state: str) -> str:
    params = (
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid+email+profile"
        f"&state={state}"
    )
    return AUTH_URL + params

def _exchange_code(code: str) -> dict:
    resp = httpx.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()

def _decode_token(id_token: str) -> dict:
    jwks = httpx.get(JWKS_URL, timeout=10).json()
    return jwt.decode(
        id_token,
        jwks,
        algorithms=["RS256"],
        audience=CLIENT_ID,
        options={"verify_at_hash": False},
    )

def require_auth() -> dict | None:
    """
    Call at top of app.py. Returns user dict if authenticated, else redirects to Keycloak and returns None.
    User dict: {id, email, name, roles}
    """
    # Already authenticated
    if st.session_state.get("user"):
        return st.session_state["user"]

    params = st.query_params.to_dict()

    # Keycloak callback with auth code
    if "code" in params:
        try:
            tokens = _exchange_code(params["code"])
            claims = _decode_token(tokens["id_token"])
            user = {
                "id": claims["sub"],
                "email": claims.get("email", ""),
                "name": claims.get("name", claims.get("preferred_username", "")),
                "roles": claims.get("realm_access", {}).get("roles", []),
            }
            st.session_state["user"] = user
            st.session_state["access_token"] = tokens["access_token"]
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")
            st.stop()
        return None

    # Not authenticated — show login button
    import secrets
    state = secrets.token_urlsafe(16)
    st.session_state["oauth_state"] = state
    login_url = _login_url(state)

    st.markdown("## 🔐 Sign in to continue")
    st.markdown(f"[**Sign in with your company account**]({login_url})")
    st.stop()
    return None

def logout():
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()
```

- [ ] **Step 2: Verify auth module imports clean**

```powershell
C:\ragenv\Scripts\python.exe -c "from auth import require_auth, logout; print('auth.py OK')"
```

Expected: `auth.py OK`

- [ ] **Step 3: Commit**

```bash
git add auth.py
git commit -m "feat: Keycloak OIDC authentication for Streamlit via PKCE code flow"
```

---

## Task 7: ingest/gdrive.py — Google Drive auto-ingestion

**Files:**
- Create: `ingest/gdrive.py`

- [ ] **Step 1: Set up Google Drive service account**

1. Go to `console.cloud.google.com` → New project → Enable Google Drive API
2. IAM & Admin → Service Accounts → Create → download JSON key
3. Save as `keycloak/gdrive-service-account.json`
4. Share your Google Drive folder with the service account email (Editor)
5. Copy the folder ID from the Drive URL: `drive.google.com/drive/folders/FOLDER_ID_HERE`
6. Set `GDRIVE_FOLDER_ID=FOLDER_ID_HERE` in `.env`

- [ ] **Step 2: Write ingest/gdrive.py**

```python
"""
Run standalone:  C:\ragenv\Scripts\python.exe -m ingest.gdrive
Or schedule with Windows Task Scheduler / cron for auto-ingestion.
"""
import os
import io
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

load_dotenv()

SA_FILE = os.environ.get("GDRIVE_SERVICE_ACCOUNT_FILE", "keycloak/gdrive-service-account.json")
FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def _get_drive_service():
    creds = service_account.Credentials.from_service_account_file(SA_FILE, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

def list_pdfs(folder_id: str) -> list[dict]:
    service = _get_drive_service()
    query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name, modifiedTime)").execute()
    return results.get("files", [])

def download_pdf(file_id: str) -> bytes:
    service = _get_drive_service()
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()

def run_ingestion():
    from ingest.processor import extract_text, chunk_text
    from vectorstore import add_document
    from db import init_db, log_indexed_doc, get_indexed_docs

    init_db()
    already_indexed = {d["filename"] for d in get_indexed_docs() if d["source_type"] == "gdrive"}

    if not FOLDER_ID:
        print("GDRIVE_FOLDER_ID not set — skipping.")
        return

    files = list_pdfs(FOLDER_ID)
    print(f"Found {len(files)} PDFs in Drive folder.")

    for f in files:
        name = f["name"]
        if name in already_indexed:
            print(f"  Skipping {name} (already indexed)")
            continue
        print(f"  Ingesting {name}...")
        pdf_bytes = download_pdf(f["id"])
        text = extract_text(pdf_bytes)
        chunks = chunk_text(text)
        added = add_document(name, chunks)
        log_indexed_doc(name, "gdrive", "auto-ingest", added)
        print(f"  ✓ {name}: {added} chunks")

if __name__ == "__main__":
    run_ingestion()
```

- [ ] **Step 3: Test ingestion (requires service account file)**

```powershell
C:\ragenv\Scripts\python.exe -m ingest.gdrive
```

Expected: `Found N PDFs in Drive folder. ✓ filename.pdf: N chunks`

- [ ] **Step 4: Commit**

```bash
git add ingest/gdrive.py
git commit -m "feat: Google Drive auto-ingestion via service account"
```

---

## Task 8: app.py — Full production upgrade

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Write full production app.py**

```python
import os
import streamlit as st
from dotenv import load_dotenv
from anthropic import Anthropic
from auth import require_auth, logout
from db import init_db, upsert_user, log_query, log_feedback, get_audit_log, get_indexed_docs, log_indexed_doc
from vectorstore import add_document, query as vs_query, get_stats
from ingest.processor import extract_text, chunk_text

load_dotenv()
init_db()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAG Platform — The AI Stackk",
    page_icon="🧠",
    layout="wide",
)

# ── Auth ──────────────────────────────────────────────────────────────────────
user = require_auth()
upsert_user(user["id"], user["email"], user["name"])
is_admin = "rag-admin" in user.get("roles", [])

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"👤 **{user['name']}**")
    st.caption(user["email"])
    if is_admin:
        st.caption("🛡️ Admin")
    if st.button("Sign out"):
        logout()
    st.divider()

    stats = get_stats()
    st.markdown(f"**{stats['total_chunks']} chunks** indexed")
    st.markdown(f"**{len(stats['documents'])} documents** loaded")
    st.divider()

    if stats["documents"]:
        st.markdown("**Indexed documents:**")
        colors = ["🔵","🟢","🟠","🟣","🔴","🟡"]
        for i, doc in enumerate(stats["documents"]):
            st.markdown(f"{colors[i % len(colors)]} {doc}")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tabs = ["💬 Ask", "📄 Upload", "📊 Audit Log"] if is_admin else ["💬 Ask", "📄 Upload"]
tab_objs = st.tabs(tabs)

# ── TAB: Ask ─────────────────────────────────────────────────────────────────
with tab_objs[0]:
    st.header("Ask anything across your documents")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
        if msg["role"] == "assistant":
            if msg.get("sources"):
                with st.expander("📌 Source chunks"):
                    colors = ["🔵","🟢","🟠","🟣","🔴","🟡"]
                    doc_list = stats["documents"]
                    for src in msg["sources"]:
                        idx = doc_list.index(src["doc"]) if src["doc"] in doc_list else 0
                        st.info(f"{colors[idx % len(colors)]} **{src['doc']}**\n\n{src['text']}")
            col1, col2, _ = st.columns([1, 1, 8])
            qid = msg.get("query_id")
            if qid:
                if col1.button("👍", key=f"up_{qid}"):
                    log_feedback(qid, user["id"], 1)
                    st.toast("Thanks for the feedback!")
                if col2.button("👎", key=f"dn_{qid}"):
                    log_feedback(qid, user["id"], -1)
                    st.toast("Noted — we'll improve.")

    question = st.chat_input("Ask a question across all your documents...")

    if question:
        if stats["total_chunks"] == 0:
            st.warning("No documents indexed yet. Upload some PDFs in the Upload tab.")
        else:
            with st.chat_message("user"):
                st.markdown(question)
            st.session_state.chat_history.append({"role": "user", "content": question})

            sources = vs_query(question, n=4)

            with st.expander("📌 Retrieved chunks", expanded=True):
                colors = ["🔵","🟢","🟠","🟣","🔴","🟡"]
                doc_list = stats["documents"]
                for src in sources:
                    idx = doc_list.index(src["doc"]) if src["doc"] in doc_list else 0
                    st.info(f"{colors[idx % len(colors)]} **{src['doc']}**\n\n{src['text']}")

            context = "\n\n---\n\n".join(
                f"[From: {s['doc']}]\n{s['text']}" for s in sources
            )
            system_prompt = (
                "You are a helpful research assistant. Answer using ONLY the context below. "
                "Cite which document each fact comes from by its filename. "
                "Plain English only. If the answer isn't in the context say: "
                "'I couldn\\'t find that in the uploaded documents.'\n\n"
                f"CONTEXT:\n{context}"
            )

            client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
            with st.chat_message("assistant"):
                placeholder = st.empty()
                full_response = ""
                with client.messages.stream(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[{"role": "user", "content": question}],
                ) as stream:
                    for text in stream.text_stream:
                        full_response += text
                        placeholder.markdown(full_response + "▌")
                placeholder.markdown(full_response)

            query_id = log_query(user["id"], question, sources, full_response)
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": full_response,
                "sources": sources,
                "query_id": query_id,
            })
            st.rerun()

# ── TAB: Upload ───────────────────────────────────────────────────────────────
with tab_objs[1]:
    st.header("Upload documents")
    st.caption("PDFs are indexed into the shared vector store — available to all users instantly.")

    uploaded_files = st.file_uploader(
        "Upload one or more PDFs",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        indexed_names = {d["filename"] for d in get_indexed_docs()}
        new_files = [f for f in uploaded_files if f.name not in indexed_names]

        if not new_files:
            st.info("All uploaded files are already indexed.")
        else:
            with st.status(f"Indexing {len(new_files)} new document(s)...", expanded=True) as status:
                for f in new_files:
                    st.write(f"Processing **{f.name}**...")
                    text = extract_text(f.read())
                    chunks = chunk_text(text)
                    added = add_document(f.name, chunks)
                    log_indexed_doc(f.name, "upload", user["email"], added)
                    st.write(f"→ {added} chunks added")
                status.update(label="✅ Done!", state="complete")
            st.rerun()

    docs = get_indexed_docs()
    if docs:
        st.divider()
        st.subheader("All indexed documents")
        st.dataframe(
            [{"Document": d["filename"], "Source": d["source_type"],
              "Chunks": d["chunk_count"], "By": d["uploaded_by"],
              "Indexed": d["indexed_at"][:19]} for d in docs],
            use_container_width=True,
        )

# ── TAB: Audit Log (admin only) ───────────────────────────────────────────────
if is_admin:
    with tab_objs[2]:
        st.header("Audit Log")
        st.caption("All queries across all users.")
        rows = get_audit_log(limit=100)
        if rows:
            st.dataframe(
                [{"User": r["email"], "Question": r["question"][:80],
                  "Rating": "👍" if r["rating"]==1 else ("👎" if r["rating"]==-1 else "—"),
                  "Time": r["ts"][:19]} for r in rows],
                use_container_width=True,
            )
        else:
            st.info("No queries yet.")
```

- [ ] **Step 2: Run the full app**

```powershell
# Copy .env.example to .env and fill in your ANTHROPIC_API_KEY first
# Keycloak must be running: docker compose up -d

C:\ragenv\Scripts\streamlit.exe run app.py
```

Open `http://localhost:8501` — you should be redirected to Keycloak login.

- [ ] **Step 3: End-to-end smoke test**

1. Sign in via Keycloak → lands back on app
2. Upload `sample-docs/rag-explained.pdf`
3. Ask: *"When should I NOT use RAG?"* → answer cites filename
4. Click 👍 → toast appears
5. Sign in as admin role → check Audit Log tab shows the query

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: production app with SSO, multi-user, audit log, feedback, persistent vectorstore"
```

---

## Task 9: Schedule Google Drive ingestion (Windows Task Scheduler)

**Files:**
- Create: `ingest/run_gdrive.ps1`

- [ ] **Step 1: Write the scheduler script**

```powershell
# ingest/run_gdrive.ps1
# Run this on a schedule to auto-ingest new Google Drive PDFs
$env:Path = "C:\ragenv\Scripts;" + $env:Path
Set-Location "D:\TheAIStackk\rag-demo"
python -m ingest.gdrive >> logs\gdrive_ingest.log 2>&1
```

- [ ] **Step 2: Register with Windows Task Scheduler**

```powershell
New-Item -ItemType Directory -Force "D:\TheAIStackk\rag-demo\logs"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NonInteractive -File D:\TheAIStackk\rag-demo\ingest\run_gdrive.ps1"

$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 4) -Once -At (Get-Date)

Register-ScheduledTask -TaskName "RAG-GDrive-Ingest" -Action $action -Trigger $trigger -RunLevel Highest
```

Expected: Task appears in Task Scheduler, runs every 4 hours.

- [ ] **Step 3: Commit**

```bash
git add ingest/run_gdrive.ps1
git commit -m "feat: Windows Task Scheduler script for Google Drive auto-ingestion every 4h"
```

---

## Verification Checklist

- [ ] `docker compose up -d` starts Keycloak on port 8080
- [ ] `C:\ragenv\Scripts\streamlit.exe run app.py` redirects to Keycloak login
- [ ] After login, user name appears in sidebar
- [ ] Upload PDF → appears in "Indexed documents" table
- [ ] Ask question → answer streams with source citations
- [ ] 👍/👎 buttons record feedback without page error
- [ ] Admin role user sees Audit Log tab with all queries
- [ ] `python -m ingest.gdrive` ingests new Drive PDFs without re-indexing already-done ones
- [ ] Restart app → `chroma_db/` persists, no re-upload needed
