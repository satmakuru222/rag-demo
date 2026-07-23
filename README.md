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
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Google Cloud project (optional, for Google Drive auto-ingestion)

---

## Configuration

### A — Get Your Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Click **API Keys** in the left sidebar
4. Click **Create Key** → give it a name (e.g. `rag-platform`)
5. Copy the key — it starts with `sk-ant-api03-...`
6. Paste it as `ANTHROPIC_API_KEY` in your `.env` file (see Section C)

> ⚠️ You will only see the key once. Store it securely.

---

### B — Set Up Google Drive Ingestion (Optional)

This allows PDFs dropped into a shared Google Drive folder to be automatically indexed every hour. Skip this section if you only want manual PDF uploads.

#### Step 1 — Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown (top left) → **New Project**
3. Name it (e.g. `rag-platform`) → click **Create**
4. Make sure the new project is selected in the dropdown

#### Step 2 — Enable the Google Drive API

1. In the left sidebar go to **APIs & Services → Library**
2. Search for **Google Drive API**
3. Click it → click **Enable**

#### Step 3 — Create a Service Account

A service account is a bot identity — it can access Drive without a human logging in.

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → Service Account**
3. Name: `rag-drive-reader` → click **Create and Continue**
4. Role: select **Viewer** → click **Continue** → click **Done**

#### Step 4 — Download the Service Account Key

1. On the Credentials page, click your new service account email
2. Go to the **Keys** tab
3. Click **Add Key → Create New Key → JSON**
4. The JSON file downloads automatically
5. Create a `credentials/` folder in your project root
6. Move the downloaded JSON there and rename it (e.g. `service-account.json`)

```
rag-demo/
└── credentials/
    └── service-account.json   ← your downloaded key (never commit this)
```

#### Step 5 — Share Your Drive Folder with the Service Account

1. Open the downloaded JSON file and find the `client_email` field — it looks like:
   `rag-drive-reader@rag-platform-xxxxx.iam.gserviceaccount.com`
2. Go to [drive.google.com](https://drive.google.com)
3. Right-click the folder you want to ingest → **Share**
4. Paste the `client_email` value → set permission to **Viewer** → click **Share**
5. Copy the folder ID from the URL:
   `https://drive.google.com/drive/folders/`**`1ABC123xyz...`** ← this is the folder ID

---

### C — Configure `.env`

```powershell
cp .env.example .env
```

Open `.env` and fill in every value:

```env
# ── Anthropic ─────────────────────────────────────────────────
# Get from: https://console.anthropic.com → API Keys
ANTHROPIC_API_KEY=sk-ant-api03-...

# ── Keycloak SSO ──────────────────────────────────────────────
# Leave these as-is for local setup
KEYCLOAK_URL=https://localhost:8443
KEYCLOAK_REALM=rag-demo
KEYCLOAK_CLIENT_ID=rag-app
KEYCLOAK_CLIENT_SECRET=rag-app-secret-2026-the-ai-stackk
REDIRECT_URI=http://localhost:8501

# ── Storage paths ─────────────────────────────────────────────
CHROMA_DB_PATH=./chroma_db
SQLITE_DB_PATH=./rag.db

# ── Google Drive (optional) ───────────────────────────────────
# Path to the service account JSON you downloaded in Step B-4
GDRIVE_SERVICE_ACCOUNT_FILE=credentials/service-account.json
# Folder ID from the Drive URL (Step B-5)
GDRIVE_FOLDER_ID=1ABC123xyz...
```

> ⚠️ `.env` and `credentials/` are in `.gitignore` — they will never be committed.

---

## Setup

### 1. Clone and create virtualenv

```powershell
git clone https://github.com/satmakuru222/rag-demo.git
cd rag-demo
python -m venv C:\ragenv
C:\ragenv\Scripts\activate
pip install -r requirements.txt
```

Mac/Linux:
```bash
python3 -m venv ragenv
source ragenv/bin/activate
pip install -r requirements.txt
```

### 2. Generate SSL certificates (for Keycloak HTTPS)

```powershell
# Install mkcert (once per machine)
mkcert -install

# Generate certs for localhost
mkdir certs
cd certs
mkcert localhost

# Copy mkcert root CA so Python (httpx) trusts it
copy "$env:LOCALAPPDATA\mkcert\rootCA.pem" rootCA.pem
cd ..
```

Mac/Linux:
```bash
mkdir certs && cd certs
mkcert localhost
cp "$(mkcert -CAROOT)/rootCA.pem" rootCA.pem
cd ..
```

### 3. Create and fill `.env`

Follow **Section C** above.

---

## Running the Platform

### Step 1 — Start Keycloak + nginx

```powershell
docker compose up -d
```

Wait ~30 seconds. Verify Keycloak is up:

```powershell
# Should return HTTP 200
Invoke-WebRequest https://localhost:8443/realms/rag-demo -SkipCertificateCheck
```

Keycloak admin console: `https://localhost:8443`
- Username: `admin` · Password: `admin123`

Default app user:
- Username: `santoshi` · Password: `demo1234` (has `rag-admin` role)

To add more users: Keycloak admin → rag-demo realm → Users → Add user

### Step 2 — Start Streamlit

```powershell
.\start.ps1
```

Or manually:
```powershell
streamlit run app.py --server.port 8501
```

### Step 3 — Open the app

Go to **`http://localhost:8501`** → click **Sign in** → log in with your Keycloak credentials.

---

## Using the App

1. **Create a notebook** — click `➕ New notebook` in the sidebar
2. **Upload sources** — go to `📄 Sources` tab → upload PDFs
3. **Ask questions** — go to `💬 Ask` tab → type your question
4. **View sources** — expand `📌 Retrieved chunks` to see what Claude read
5. **Give feedback** — click 👍 or 👎 on any response
6. **Switch notebooks** — click any notebook in the sidebar
7. **Delete sources** — click 🗑️ next to any source in the Sources tab

Admin users also see `📊 Audit Log` — all queries across all users.

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

Google Drive ──► ingest/gdrive.py (hourly) ──► ChromaDB
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
├── start.ps1               # Start script (Windows)
├── docker-compose.yml      # Keycloak + nginx
├── .env                    # Secrets — never committed
├── .env.example            # Template with instructions
├── .gitignore
├── keycloak/
│   └── realm-export.json   # Pre-configured realm (imported on first boot)
├── nginx/
│   └── nginx.conf          # HTTPS reverse proxy config
├── certs/
│   ├── localhost.pem       # SSL cert — never committed
│   ├── localhost-key.pem   # SSL key — never committed
│   └── rootCA.pem          # mkcert CA root (safe to commit)
├── credentials/            # Google service account JSON — never committed
├── ingest/
│   ├── processor.py        # PDF text extraction + chunking
│   └── gdrive.py           # Google Drive polling + ingestion
├── docs/
│   └── scripts/            # Presentation scripts + YouTube episode notes
└── sample-docs/            # Sample PDFs for testing
```

---

## Restarting After Shutdown

```powershell
docker compose up -d   # Keycloak data persists in Docker volume
.\start.ps1            # Streamlit
```

> `docker compose down` keeps data. `docker compose down -v` wipes the Keycloak volume (resets users/config).

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `ERR_CONNECTION_REFUSED` on login redirect | Streamlit crashed — rerun `.\start.ps1` |
| `Token exchange failed 401` | Client secret mismatch — check `KEYCLOAK_CLIENT_SECRET` in `.env` matches `keycloak/realm-export.json` |
| `502 Bad Gateway` on Keycloak | Keycloak still booting — wait 30s and retry |
| `Service account file not found` | Check `GDRIVE_SERVICE_ACCOUNT_FILE` path in `.env` |
| `Found 0 PDFs` in Drive ingestion | Drive folder not shared with service account `client_email` |
| Duplicate notebooks created | Fixed — the Create button now guards against double-fire |

---

## Tech Stack

- [Streamlit](https://streamlit.io) — Python web UI
- [ChromaDB](https://www.trychroma.com) — local vector database
- [Keycloak](https://www.keycloak.org) — open-source SSO / identity provider
- [nginx](https://nginx.org) — HTTPS reverse proxy
- [Claude claude-sonnet-4-6](https://www.anthropic.com) — LLM generation
- [Docker](https://www.docker.com) — container runtime
- [SQLite](https://sqlite.org) — lightweight relational database
- [Google Drive API](https://developers.google.com/drive) — document auto-ingestion
- [python-jose](https://github.com/mpdavis/python-jose) — JWT validation
- [httpx](https://www.python-httpx.org) — HTTP client with SSL support
- [mkcert](https://github.com/FiloSottile/mkcert) — locally-trusted SSL certificates

---

## Built by The AI Stackk

YouTube: [The AI Stackk](https://youtube.com/@theaistackk)
Episode: *Build a Production RAG Platform from Scratch*
