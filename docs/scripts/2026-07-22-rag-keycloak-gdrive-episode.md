# Episode Script: Build Your Own Private NotebookLM — RAG + SSO + Google Drive
**The AI Stackk**
Duration est: 18–22 min | Format: Long-form tutorial
Status: Draft

---

## YouTube Title Options
1. I Built a Private NotebookLM in Python — RAG + Login + Google Drive Auto-Sync
2. Build a RAG System From Scratch — With SSO Login and Google Drive (Step by Step)
3. What is RAG? — And How to Build One That Actually Works in Production

## YouTube Description
In this episode, I build a complete RAG system from scratch — plain English, step by step.

We start with the core concept: what RAG is and why it matters. Then I show you a working demo where you upload any PDF and ask it questions. Then we add company-grade login with Keycloak SSO. Then we connect Google Drive so it auto-ingests your documents.

By the end you have a private NotebookLM — your documents, your server, your rules.

Chapters:
00:00 — What is RAG?
03:30 — Live demo: upload a PDF and ask it questions
07:00 — Why you need login for a real system
09:00 — Adding Keycloak SSO (step by step)
13:00 — Connecting Google Drive auto-ingestion
17:00 — The full system running live
19:30 — Safe usage + when NOT to use RAG

Stack used: Python · Streamlit · ChromaDB · Claude API · Keycloak · Google Drive API

---

## HOOK (0:00–0:30)

**[Screen: show NotebookLM logo, then cut to your Streamlit app side by side]**

You have probably heard of NotebookLM — Google's tool that lets you upload documents and ask AI questions about them.

It is genuinely useful. But there is one problem.

Your documents go to Google.

For personal notes, that is fine. For company documents, legal contracts, patient records, or internal research — that is a problem.

Today I am going to show you how to build the same thing yourself. Your documents stay on your machine. You control who logs in. And it costs you nothing except API calls.

We are calling it RAG. Let me explain what that means.

---

## PART 1 — WHAT IS RAG? (0:30–3:30)

**[Screen: blank whiteboard or simple slide]**

RAG stands for Retrieval-Augmented Generation.

I know that sounds like a lot. Break it down:

- **Retrieval** — finding the right information
- **Augmented** — adding that information to your question
- **Generation** — Claude generates an answer using it

Here is the plain English version.

Think of Claude like a very smart new employee. On their first day, they know a lot about the world — history, science, coding, writing. But they have never read your company handbook. They have never seen your internal reports. They do not know your products.

RAG is how you give them the handbook.

**[Screen: simple diagram — PDF → chunks → vectors → question → answer]**

Here is how it works in three steps.

**Step one: Chunk.**
Your document gets split into small pieces. About 500 characters each. Think of it like cutting a book into index cards.

**Step two: Retrieve.**
When you ask a question, the system finds the index cards most relevant to your question. Not by keyword — by meaning. "What should I not do?" will find cards about warnings and limitations even if they use different words.

**Step three: Generate.**
Claude reads only those cards and writes you an answer. It tells you which document the answer came from.

That is RAG. Three steps. Upload, search, answer.

**[Screen: show the "when NOT to use RAG" list]**

One quick safe usage note before we build.

RAG is not the right tool for everything.

Do not use RAG for general questions — just ask Claude directly, it already knows.

Do not use RAG for short documents — if it fits in one paste, just paste it.

Do not use RAG for spreadsheets or tables — the chunking will break the structure.

Use RAG when you have private documents the AI has never seen, and you need answers grounded in a specific source.

Alright. Let us build it.

---

## PART 2 — LIVE DEMO: BASIC RAG (3:30–7:00)

**[Screen: VS Code showing app.py, then switch to browser at localhost:8501]**

I have a Streamlit app running. Four files. No frameworks. No complex setup.

Here is the structure:

```
app.py          ← the entire UI and pipeline
vectorstore.py  ← ChromaDB handles the search
ingest/
  processor.py  ← splits PDFs into chunks
```

Let me walk through what happens when you upload a PDF.

**[Screen: drag sample PDF into the uploader]**

I am uploading this PDF — a plain English guide to RAG I wrote for this demo.

Watch what happens.

**[Screen: status box showing "Extracting text... Splitting into chunks... Embedding into ChromaDB..."]**

Step one — it reads the PDF. PyPDF2 extracts all the text.

Step two — it splits that text into 500-character chunks with 50-character overlap. The overlap is important — it makes sure no sentence gets cut in half.

Step three — ChromaDB embeds every chunk into a vector. A vector is just a list of numbers that captures the meaning of that text. Similar meanings end up close together.

Click that expander — you can see the actual chunks.

**[Screen: expand chunk preview, show 4 chunks of text]**

Each chunk is a standalone piece of your document. The AI will only ever read the 3 or 4 most relevant ones.

Now let me ask a question.

**[Screen: type in chat input "When should I NOT use RAG?"]**

I am asking: "When should I NOT use RAG?"

**[Screen: show the retrieved chunks expanding, then Claude streaming the answer]**

See those highlighted chunks? That is the retrieval step. The system found the most relevant parts of my document — the ones that talk about limitations.

And now Claude is reading only those chunks and writing the answer.

**[Screen: answer finishes streaming, shows source citation]**

Notice it says where the answer came from. That is source grounding. You can verify it.

Now let me ask something that is NOT in the document.

**[Screen: type "What is the weather in New York today?"]**

**[Screen: Claude says "I couldn't find that in the uploaded documents."]**

It says it does not know. It does not make something up. That is the right behavior.

This is RAG. It only answers from your documents.

---

## PART 3 — THE PROBLEM WITH A SINGLE USER (7:00–9:00)

**[Screen: show the simple app running]**

What we built so far is great for personal use.

But imagine you want to use this at work. Multiple people need to access it. You need to know who asked what. You need to control who can upload documents.

Right now, anyone who finds the URL gets full access. No login. No audit trail. No idea who did what.

That is not production-ready.

So we are going to add three things.

**[Screen: simple checklist appears]**

One — **Keycloak SSO login.** Only people with a company account can access the app.

Two — **Audit logs.** Every question and every answer is recorded with the user's name and timestamp.

Three — **Google Drive auto-ingestion.** Instead of manually uploading PDFs, any document added to a shared Drive folder gets indexed automatically.

Let us start with login.

---

## PART 4 — ADDING KEYCLOAK SSO (9:00–13:00)

**[Screen: show docker-compose.yml]**

Keycloak is an open-source identity provider. It is what companies use instead of building their own login system.

We run it in Docker. One command.

```powershell
docker compose up -d
```

**[Screen: show Docker Desktop, container starting]**

That spins up a Keycloak server on port 8080. It comes with a pre-configured realm called `rag-demo` that I set up in a config file.

**[Screen: open localhost:8080, show Keycloak admin UI]**

This is the Keycloak admin panel. Think of a realm as your company's workspace. Inside it, I have one app registered — `rag-app` — with a redirect URI pointing to our Streamlit app.

**[Screen: show Clients → rag-app → Settings]**

The key settings are:

- **Client authentication ON** — this is a confidential client, it has a secret
- **Standard flow enabled** — this is the login redirect flow
- **Valid redirect URIs** — `http://localhost:8501/*` — where Keycloak sends users after login

**[Screen: show Credentials tab, regenerate button]**

I generate a client secret here and paste it into my `.env` file. This secret is how the app proves to Keycloak that it is the real app and not something pretending to be it.

Now let me show you the auth flow in the code.

**[Screen: show auth.py]**

```python
def require_auth():
    if st.session_state.get("user"):
        return st.session_state["user"]  # already logged in

    if "code" in st.query_params:
        # Keycloak sent us back a code — exchange it for a token
        tokens = _exchange_code(code)
        claims = _decode_token(tokens["id_token"])
        st.session_state["user"] = {
            "id": claims["sub"],
            "email": claims.get("email"),
            "name": claims.get("name"),
            "roles": claims.get("realm_access", {}).get("roles", []),
        }
        st.rerun()

    # Not logged in — show login link
    st.markdown(f"[Sign in with your company account →]({login_url})")
    st.stop()
```

Plain English: check if logged in, if not, redirect to Keycloak, when Keycloak sends the user back with a code, exchange that code for a real token, read the user's email and roles from the token, done.

**[Screen: show Streamlit app with login page]**

When the app starts now, you see this.

**[Screen: click login link, redirects to Keycloak login page at localhost:8080]**

Click that link — goes to Keycloak.

**[Screen: type username and password at Keycloak]**

Type your credentials. This is your company login page — you would customize it with your logo and colors in a real deployment.

**[Screen: Keycloak redirects back to localhost:8501, user name appears in sidebar]**

And we are back. The user's name is in the sidebar. The audit log records every question they ask.

I can also assign roles. If I give someone the `rag-admin` role, they see an extra tab — the Audit Log — showing every query across every user with ratings.

**[Screen: show Audit Log tab with a table of queries, users, ratings]**

This is what an enterprise system needs. You know who asked what, when, and whether the answer was useful.

---

## PART 5 — GOOGLE DRIVE AUTO-INGESTION (13:00–17:00)

**[Screen: show Google Cloud Console]**

The last piece is automatic document ingestion from Google Drive.

Right now, someone has to manually upload PDFs into the app. In a company, that means IT or whoever manages the system has to do it every time there is a new document. That does not scale.

The fix: connect a Google Drive folder. Anything added there gets indexed automatically every four hours.

Here is the setup. It takes about five minutes.

**[Screen: console.cloud.google.com]**

Go to Google Cloud Console. Create a project. Enable the Google Drive API.

**[Screen: IAM → Service Accounts]**

Create a service account. This is like creating a robot user that our app can use to read Drive files without requiring a human to log in. Download its JSON key file.

**[Screen: Google Drive, right-click folder → Share]**

Share your Drive folder with the service account's email address. Give it Viewer access. That is it — the service account can now read files in that folder.

**[Screen: show .env with GDRIVE_FOLDER_ID filled in]**

Grab the folder ID from the Drive URL and paste it in your `.env`.

**[Screen: show ingest/gdrive.py]**

The ingestion script does four things.

```python
def run_ingestion():
    already_indexed = {d["filename"] for d in get_indexed_docs()}
    files = list_pdfs(FOLDER_ID)

    for f in files:
        if f["name"] in already_indexed:
            continue  # skip — already done
        pdf_bytes = download_pdf(f["id"])
        chunks = chunk_text(extract_text(pdf_bytes))
        add_document(f["name"], chunks)
        log_indexed_doc(f["name"], "gdrive", "auto-ingest", len(chunks))
```

Check what is already indexed. List new PDFs in the folder. Download, chunk, embed, log. Skip anything already done.

**[Screen: run python -m ingest.gdrive in terminal]**

```
Found 3 PDFs in Drive folder.
  Ingesting company-policy.pdf...
  ✓ company-policy.pdf: 47 chunks added
  Ingesting onboarding-guide.pdf...
  ✓ onboarding-guide.pdf: 83 chunks added
```

**[Screen: show Windows Task Scheduler]**

And we schedule it to run every four hours with Windows Task Scheduler. One PowerShell script, one command as administrator, done. New documents in Drive get indexed while you sleep.

---

## PART 6 — THE FULL SYSTEM LIVE (17:00–19:30)

**[Screen: full app running with multiple docs in sidebar]**

Let me show you the full system.

I have three documents indexed — a company policy guide, an onboarding handbook, and a technical FAQ. All came in automatically from Google Drive.

**[Screen: Ask tab, type "What is the vacation policy?"]**

I ask: "What is the vacation policy?"

**[Screen: show retrieved chunks from company-policy.pdf, Claude streams answer]**

It retrieves from the policy document, cites it by filename, and answers. Accurate. Sourced.

**[Screen: click 👍 button]**

I click thumbs up. That rating goes into the audit log.

**[Screen: switch to admin user, show Audit Log tab]**

As admin I can see every question asked across all users — who asked, what they asked, and whether they found the answer useful.

**[Screen: show Upload tab with indexed docs table]**

And in the Upload tab I can see every document in the system — where it came from, how many chunks, who added it, when.

This is a private NotebookLM. Your data. Your server. Your rules.

---

## SAFE USAGE + RECAP (19:30–21:00)

**[Screen: cheat sheet slide]**

Before I wrap up — three safe usage reminders.

**One.** RAG answers from your documents. It does not browse the internet. If your documents are outdated, the answers will be too. Keep your Drive folder current.

**Two.** Do not upload sensitive personal data — medical records, financial credentials, passwords — to any RAG system without checking your company's data policy first. Even a private system has attack surface.

**Three.** Always tell users what documents the system has access to. If someone asks a question and the answer is not in any document, the system should say so — and ours does.

**[Screen: recap cheat sheet]**

Here is what we built today:

```
Basic RAG      → upload PDF → ask questions → cited answers
Multi-user     → Keycloak SSO → login redirect → token validation
Audit trail    → every query logged → admin dashboard
Auto-ingestion → Google Drive folder → indexed every 4 hours
```

The full code is linked in the description. Everything runs locally.

---

## CTA (21:00–21:30)

**[Screen: outro card]**

If this was useful, follow The AI Stackk for one AI concept at a time — plain English, real examples, no jargon.

Next episode: I will show you how to add a local LLM to this same system so it runs with zero API costs.

Comment below — what documents would you most want to query with a system like this?

---

## B-ROLL / SCREEN RECORDING CHECKLIST

- [ ] Streamlit app upload animation (PDF drag and drop)
- [ ] Chunk preview expander opening
- [ ] Claude streaming answer in real time
- [ ] Keycloak login page and redirect back
- [ ] Audit log table with multiple users and ratings
- [ ] Google Drive folder with PDFs, terminal showing ingestion
- [ ] Windows Task Scheduler showing scheduled task
- [ ] Full demo: 3 docs loaded, question asked, answer with source

## THUMBNAIL IDEAS

1. Split screen: NotebookLM logo (crossed out) vs your Streamlit app (glowing) + text "Build Your Own"
2. Terminal showing `Found 3 PDFs` + Keycloak login screen + text "Private AI Document Search"
3. Simple: PDF icon → brain icon → answer bubble + "Your Docs. Your Server. Your Rules."
