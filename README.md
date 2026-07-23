# RAG Platform — The AI Stackk

A production-grade RAG (Retrieval-Augmented Generation) platform built with Streamlit, ChromaDB, Keycloak SSO, and Claude. Multi-notebook document Q&A — like NotebookLM, but self-hosted and enterprise-ready.

**Features:**
- 🔐 Keycloak SSO (OIDC) — company login, no new passwords
- 📚 Notebooks — isolated document collections per topic
- 📄 PDF upload + delete per source
- 🤖 Claude claude-sonnet-4-6 with streaming responses + source citations
- 📁 Google Drive auto-ingestion (polls hourly)
- 📋 Audit log + 👍/👎 feedback loop (admin only)
- 🗄️ ChromaDB (persistent vector store) + SQLite

---

## Prerequisites

- Python 3.10+
- Docker Desktop (running)
- `mkcert` installed ([docs](https://github.com/FiloSottile/mkcert))
- Anthropic API key
- Google Drive service account JSON (optional, for auto-ingestion)

---

## Setup

### 1. Clone and create virtualenv

```bash
git clone <this-repo>
cd rag-demo
python -m venv C:\ragenv
C:\ragenv\Scripts\activate       # Windows
# source /path/to/ragenv/bin/activate  # Mac/Linux
pip install -r requirements.txt
```

### 2. Generate SSL certificates (for Keycloak HTTPS)

```powershell
mkcert -install
mkdir certs
cd certs
mkcert localhost
# Copy the mkcert root CA so Python trusts it:
copy "$env:LOCALAPPDATA\mkcert\rootCA.pem" rootCA.pem
cd ..
```

### 3. Create `.env`

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
ANTHROPIC_API_KEY=sk-ant-...
KEYCLOAK_URL=https://localhost:8443
KEYCLOAK_REALM=rag-demo
KEYCLOAK_CLIENT_ID=rag-app
KEYCLOAK_CLIENT_SECRET=rag-app-secret-2026-the-ai-stackk
REDIRECT_URI=http://localhost:8501
CHROMA_DB_PATH=./chroma_db
SQLITE_DB_PATH=./rag.db
GDRIVE_SERVICE_ACCOUNT_FILE=credentials/your-service-account.json
GDRIVE_FOLDER_ID=your_google_drive_folder_id
```

> ⚠️ Never commit `.env`. It is in `.gitignore`.

### 4. (Optional) Google Drive ingestion

- Create a service account in Google Cloud Console with Drive API enabled
- Download the JSON key → save to `credentials/your-service-account.json`
- Share your Drive folder with the service account email address
- Set `GDRIVE_FOLDER_ID` in `.env`

> ⚠️ Never commit the `credentials/` folder. It is in `.gitignore`.

---

## Running the Platform

### Step 1 — Start Keycloak + nginx (Docker)

```powershell
cd rag-demo
docker compose up -d
```

Wait ~30 seconds for Keycloak to boot and import the realm.

Verify: open `https://localhost:8443` — you should see the Keycloak welcome page.

Admin console: `https://localhost:8443` → Administration Console
- Username: `admin`
- Password: `admin123`

### Step 2 — Start Streamlit

```powershell
.\start.ps1
```

Or manually:

```powershell
$env:PATH = "C:\ragenv\Scripts;" + $env:PATH
streamlit run app.py --server.port 8501
```

### Step 3 — Open the app

Go to: `http://localhost:8501`

Login with:
- Username: `santoshi`
- Password: `demo1234`

---

## Using the App

1. **Create a notebook** — click `➕ New notebook` in the sidebar, give it a name
2. **Upload sources** — go to `📄 Sources` tab, upload one or more PDFs
3. **Ask questions** — go to `💬 Ask` tab, type your question
4. **View sources** — expand `📌 Retrieved chunks` to see exactly what Claude read
5. **Give feedback** — click 👍 or 👎 on any response
6. **Switch notebooks** — click any notebook in the sidebar to switch context
7. **Delete sources** — click 🗑️ next to any source in the Sources tab

Admin users also see the `📊 Audit Log` tab with all queries across all users.

---

## Architecture

```
Browser
  │
  ├─[login]──► nginx (8443, HTTPS) ──► Keycloak (8080, internal)
  │
  └─[app]───► Streamlit (8501, HTTP)
                    │
                    ├─[upload]──► ChromaDB (./chroma_db/)
                    ├─[ask]────► ChromaDB → Claude API → streamed answer
                    └─[log]────► SQLite (./rag.db)

Google Drive ──► ingest/gdrive.py (hourly cron) ──► ChromaDB
```

| Component | Purpose |
|---|---|
| Streamlit | Web UI |
| Keycloak | SSO / OIDC identity provider |
| nginx | HTTPS termination for Keycloak |
| ChromaDB | Vector store (embeddings + semantic search) |
| SQLite | Users, notebooks, audit log, feedback |
| Claude claude-sonnet-4-6 | Answer generation |
| Google Drive API | Auto-ingest PDFs from shared folder |

---

## File Structure

```
rag-demo/
├── app.py                  # Main Streamlit app
├── auth.py                 # Keycloak OIDC auth
├── db.py                   # SQLite layer
├── vectorstore.py          # ChromaDB wrapper
├── requirements.txt
├── start.ps1               # Start script
├── docker-compose.yml      # Keycloak + nginx
├── .env                    # Secrets (not committed)
├── .env.example            # Template
├── .gitignore
├── keycloak/
│   └── realm-export.json   # Pre-configured realm (imported on first boot)
├── nginx/
│   └── nginx.conf          # HTTPS reverse proxy config
├── certs/
│   ├── localhost.pem       # SSL cert (not committed)
│   ├── localhost-key.pem   # SSL key (not committed)
│   └── rootCA.pem          # mkcert CA (safe to commit)
├── credentials/            # Google service account (not committed)
├── ingest/
│   ├── processor.py        # PDF extraction + chunking
│   └── gdrive.py           # Google Drive polling
├── docs/
│   └── scripts/            # YouTube episode scripts + presentation
└── sample-docs/            # Sample PDFs for testing
```

---

## Restarting After Shutdown

```powershell
# Start Keycloak (data is persisted in Docker volume)
docker compose up -d

# Start Streamlit
.\start.ps1
```

> Note: `docker compose down` preserves data. `docker compose down -v` deletes the Keycloak volume (resets all users/config).

---

## Tech Stack

- [Streamlit](https://streamlit.io) — Python web UI
- [ChromaDB](https://www.trychroma.com) — local vector database
- [Keycloak](https://www.keycloak.org) — open-source SSO
- [nginx](https://nginx.org) — reverse proxy / SSL termination
- [Claude claude-sonnet-4-6](https://www.anthropic.com) — LLM generation
- [Docker](https://www.docker.com) — container runtime
- [SQLite](https://sqlite.org) — lightweight relational database
- [Google Drive API](https://developers.google.com/drive) — document ingestion
- [python-jose](https://github.com/mpdavis/python-jose) — JWT validation
- [httpx](https://www.python-httpx.org) — async HTTP client
- [mkcert](https://github.com/FiloSottile/mkcert) — locally-trusted SSL certs

---

## Built by The AI Stackk

YouTube: [The AI Stackk](https://youtube.com/@theaistackk)  
Episode: *Build a Production RAG Platform from Scratch*
