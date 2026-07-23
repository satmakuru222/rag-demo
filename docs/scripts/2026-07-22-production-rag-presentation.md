# Production RAG Platform — Presentation Script & Slide Guide
**The AI Stackk | Episode: Build a Production RAG Platform from Scratch**

> **How to use this file:**
> Each `## SLIDE N` block = one slide.
> "**VISUAL**" = what goes on the slide.
> "**SCRIPT**" = what you say out loud.
> Estimated runtime: **22–25 minutes**

---

## SLIDE 1 — Title Slide

**VISUAL:**
> Headline: *"Build a Production RAG Platform — Like NotebookLM, but Yours"*
> Subline: The AI Stackk | Open Source · Self-Hosted · Enterprise-Ready
> Your logo + date

**SCRIPT:**
"What if you could build your own NotebookLM — one that runs on your company's servers, connects to your Google Drive, enforces SSO login, and keeps every query in an audit trail? That's exactly what we're going to build today, from scratch, step by step. By the end of this video you'll understand RAG deeply, and you'll have a working platform you can show to any engineering or IT team and say — we can run this ourselves."

---

## SLIDE 2 — The Problem (Why This Matters)

**VISUAL:**
> Split screen:
> LEFT: Generic AI (ChatGPT / Claude) — "Knows the internet, not your company"
> RIGHT: Your documents — Product manuals, SOPs, legal docs, internal wikis
> Big arrow between them with a ❌

**SCRIPT:**
"Every company I talk to has the same frustration. They try ChatGPT or Claude, and it's brilliant — until they ask it about their own product, their own policies, their own internal knowledge. Then it either makes things up or says it doesn't know. The problem is these models were trained on the internet, not on your data. RAG solves this."

---

## SLIDE 3 — What is RAG? (Plain English)

**VISUAL:**
> Three steps in a horizontal flow:
> 1. 📄 **Your Docs** → chunk into paragraphs
> 2. 🔍 **Search** → find the most relevant chunks
> 3. 🤖 **Claude** → answer using only those chunks
> Caption: "RAG = Give the AI the right pages before asking the question"

**SCRIPT:**
"RAG stands for Retrieval-Augmented Generation. Let me break that down without the jargon. Imagine you have a 500-page technical manual. Instead of feeding the whole thing to an AI — which is expensive and often impossible — you slice it into paragraphs. When someone asks a question, you first search those paragraphs to find the 3 or 4 most relevant ones, then hand ONLY those paragraphs to Claude and say 'answer using this'. The AI doesn't need to memorize your documents. It just needs to read the right page at the right time. That's RAG."

---

## SLIDE 4 — RAG vs Fine-Tuning vs Context Window

**VISUAL:**
> Comparison table:
> | | RAG | Fine-Tuning | Stuffing context |
> |---|---|---|---|
> | Update docs? | Instant | Re-train (days/$$) | Re-paste |
> | Cost | Low | High | Medium |
> | Source citations | ✅ | ❌ | ✅ |
> | Works on private data | ✅ | ✅ | ✅ |
> | Production-ready | ✅ | ✅ | ⚠️ |

**SCRIPT:**
"People always ask — why not just fine-tune the model on your data? Or why not just paste all your documents into the prompt? Here's the honest answer. Fine-tuning is expensive, takes days, and every time your documents change you have to do it again. Stuffing your whole context window works for small docs but falls apart at scale. RAG hits the sweet spot — you can add or update documents instantly, costs almost nothing extra per query, and you get source citations so you know exactly where the answer came from."

---

## SLIDE 5 — What We're Building Today

**VISUAL:**
> Architecture diagram — left to right:
> [Browser] → [Streamlit App]
>                  ↓ auth
>             [Keycloak SSO]
>                  ↓ query
>             [ChromaDB Vector Store]
>                  ↓ chunks
>             [Claude claude-sonnet-4-6]
>                  ↓ answer
>             [User sees response + sources]
> Below: [Google Drive] → auto-ingest → [ChromaDB]
> Below: [SQLite] ← audit log, feedback, notebooks

**SCRIPT:**
"Here's everything we're building. A Streamlit web app with Keycloak for SSO — meaning your team logs in with their company account, not a new username and password. ChromaDB stores your document embeddings locally, so your data never leaves your infrastructure. Claude generates the answers. Google Drive auto-ingests PDFs from a shared folder. And SQLite keeps an audit trail of every query, every piece of feedback, every user. Let's build it."

---

## SLIDE 6 — Step 1: Basic RAG in 50 Lines

**VISUAL:**
> Code snippet — `app.py` core logic:
> ```python
> # 1. Extract text from PDF
> text = extract_text(pdf_bytes)
>
> # 2. Chunk into paragraphs
> chunks = chunk_text(text, size=500, overlap=50)
>
> # 3. Store in ChromaDB
> collection.add(documents=chunks, ids=[...])
>
> # 4. Find relevant chunks
> results = collection.query(query_texts=[question], n_results=4)
>
> # 5. Ask Claude
> response = claude.messages.create(
>     system=f"Answer using only this context:\n{context}",
>     messages=[{"role": "user", "content": question}]
> )
> ```

**SCRIPT:**
"The core of RAG is surprisingly simple. Five steps. Extract the text. Break it into chunks — we use 500 characters with 50 character overlap so context doesn't get cut off mid-sentence. Store those chunks in ChromaDB which turns them into mathematical vectors. When a question comes in, ChromaDB finds the 4 closest matching chunks. Then we send those chunks plus the question to Claude and say 'answer from this, nothing else'. That's it. Everything else we're adding today is production engineering around this core."

---

## SLIDE 7 — Step 2: Multi-Doc & Notebooks

**VISUAL:**
> NotebookLM screenshot on left, our app on right side-by-side
> Right side shows: sidebar with notebook list, ➕ button, per-notebook sources
> Caption: "Each notebook = isolated vector store collection"

**SCRIPT:**
"Once the basic flow works, the next question is: how do we handle multiple topics? If I upload Red Hat documentation AND our company handbook, I don't want questions about HR policy pulling in Linux kernel answers. The solution is notebooks — exactly like NotebookLM. Each notebook gets its own isolated ChromaDB collection. Switch notebooks, switch context. You can delete individual sources, create fresh notebooks, and nothing bleeds across. This is what makes it feel like a proper product, not a prototype."

---

## SLIDE 8 — Step 3: Keycloak SSO

**VISUAL:**
> Flow diagram:
> [User clicks Sign In] → [Redirected to Keycloak login page]
> → [Enters company credentials] → [Keycloak issues JWT token]
> → [App validates token] → [User is in, with name + email + roles]
> Below: small diagram showing nginx → Keycloak → Streamlit

**SCRIPT:**
"This is the feature that takes it from a demo to something you can actually deploy at a company. Keycloak is an open-source identity provider — the same technology used by Red Hat, NASA, and thousands of enterprises. We run it in Docker, behind nginx for HTTPS. When a user visits the app, they're redirected to the Keycloak login page. After they authenticate, Keycloak sends back a signed JWT token. Our app validates that token and extracts the user's name, email, and roles. No custom auth code. No password storage. Just OIDC — the same standard used by Google and Microsoft login."

---

## SLIDE 9 — Step 4: Google Drive Auto-Ingestion

**VISUAL:**
> Diagram:
> [Google Drive Folder] → (Service Account polls every hour)
> → [New PDFs detected] → [Download → Chunk → Embed]
> → [ChromaDB] → [Available to all users instantly]
> Caption: "Zero-touch document pipeline"

**SCRIPT:**
"The most powerful feature for enterprise use. You set up a Google Drive folder, share it with a service account, and any PDF dropped in that folder automatically gets indexed into your RAG platform within the hour. Your team doesn't log into the app to upload documents — they just drop files into a shared Drive folder the way they already work. The ingestion script checks for new files, skips anything already indexed, and the content is searchable within minutes. This is how you get adoption — zero new workflows for your team."

---

## SLIDE 10 — Step 5: Audit Log & Feedback Loop

**VISUAL:**
> Screenshot of Audit Log tab showing:
> Table with columns: Notebook | User | Question | Rating | Time
> Two rows with 👍 and 👎 in Rating column
> Caption: "Full visibility into how your team uses the platform"

**SCRIPT:**
"Enterprise deployments need accountability. Every query is logged — who asked it, in which notebook, what the answer was, and whether the user rated it helpful or not. Admins see a full audit log. The thumbs up/thumbs down buttons on every response feed into a feedback table you can use to improve your chunking strategy, identify gaps in your documentation, or flag answers that need review. This is how you go from 'we have a RAG tool' to 'we understand how our team is using it'."

---

## SLIDE 11 — Architecture Summary (What's Running)

**VISUAL:**
> Clean infrastructure diagram:
>
> **Local / On-Premise**
> ┌─────────────────────────────────────┐
> │  Docker: Keycloak + nginx (port 8443) │
> │  Streamlit app     (port 8501)        │
> │  ChromaDB          (./chroma_db/)     │
> │  SQLite            (./rag.db)         │
> └─────────────────────────────────────┘
>
> **External (API calls only)**
> ┌──────────────────┐   ┌─────────────────┐
> │  Anthropic API   │   │  Google Drive   │
> │  (generation)    │   │  (source docs)  │
> └──────────────────┘   └─────────────────┘

**SCRIPT:**
"Let's look at what's actually running. Everything sensitive — your documents, your user data, your query history — lives on your own infrastructure. Docker runs Keycloak and nginx. Streamlit is your web interface. ChromaDB and SQLite are just folders on disk. The only external calls are to the Anthropic API for generating responses — and even that can be swapped for a self-hosted model if you need full air-gap deployment. Google Drive is optional. This is a stack a mid-sized company could run on a single VM and trust their IT team to manage."

---

## SLIDE 12 — Live Demo

**VISUAL:**
> Screen share of the running app
> Steps to show:
> 1. Open `http://localhost:8501`
> 2. Click Sign in → Keycloak login
> 3. Create a notebook "Red Hat AI Docs"
> 4. Go to Sources → upload the Red Hat PDF
> 5. Go to Ask → ask "How do I get started with AI inference?"
> 6. Show the source chunks used
> 7. Click 👍
> 8. Show Audit Log

**SCRIPT:**
"Let me show you this live. I'm opening the app — you see the sign-in screen immediately, nothing is accessible without authentication. I click sign in, I'm redirected to Keycloak, I log in with my credentials, and I'm back in the app. First thing I do is create a notebook — I'll call it 'Red Hat AI Docs'. Now I go to Sources, upload the Red Hat AI Inference getting-started guide. Watch the indexing — it's chunking and embedding in real time. Now I go to Ask and type... 'How do I get started with AI inference on Red Hat?' — see those retrieved chunks expand? Those are the exact paragraphs Claude is reading right now. And there's the answer, with the source document cited. I click thumbs up. Now if I switch to the Audit Log as admin, I can see my query, the notebook, and the rating — all logged."

---

## SLIDE 13 — How This Compares to NotebookLM

**VISUAL:**
> Side-by-side comparison:
> | Feature | NotebookLM | This Platform |
> |---|---|---|
> | Your data stays on-prem | ❌ | ✅ |
> | SSO / company auth | ❌ | ✅ |
> | Audit log | ❌ | ✅ |
> | Notebooks / isolation | ✅ | ✅ |
> | Source citations | ✅ | ✅ |
> | Auto-ingest from Drive | ❌ | ✅ |
> | Customizable AI model | ❌ | ✅ |
> | Cost at scale | Per user/mo | API calls only |

**SCRIPT:**
"NotebookLM is an incredible product. But when I talk to enterprise teams, three things always come up. First — data sovereignty. They can't send confidential documents to Google. Second — authentication. They need SSO with their existing identity provider, not Google accounts. Third — audit trails. Regulated industries need to know who asked what and when. Our platform checks all three boxes. And because you control the model, you can swap Claude for a self-hosted Llama or Mistral if you need complete air-gap operation."

---

## SLIDE 14 — When to Recommend This

**VISUAL:**
> Two columns:
>
> **✅ Use This When:**
> - Company has sensitive/confidential docs
> - Need SSO with existing identity provider
> - Regulated industry (finance, health, legal, govt)
> - Want audit trail of AI usage
> - Need to customize the AI model
> - Team already uses Google Drive
>
> **⚠️ Stick with NotebookLM When:**
> - Small team, no IT support
> - Documents aren't sensitive
> - Need audio overviews / podcast feature
> - Just exploring / prototyping

**SCRIPT:**
"So when do you recommend this over NotebookLM? If you're talking to a financial services company, a healthcare organization, a law firm, a government agency — or really any company where documents are confidential and IT security has opinions — this is the answer. If someone is a solo creator or a small startup who just wants to chat with their docs and doesn't care about data residency — honestly, just use NotebookLM. The right tool for the right situation."

---

## SLIDE 15 — What to Build Next

**VISUAL:**
> Roadmap boxes:
> Phase 2: 🔒 Role-based access per notebook | 📊 Analytics dashboard | 🔄 Slack integration
> Phase 3: 🤖 Swap to self-hosted model (Ollama/vLLM) | ☁️ Deploy to OpenShift/Kubernetes | 📧 Email digest of top queries

**SCRIPT:**
"This is a solid v1. Here's where you take it next. Role-based access so certain notebooks are only visible to certain teams. A proper analytics dashboard showing which questions get asked most, which documents get used most. Slack integration so teams can query from Slack without opening a browser. And for full air-gap deployments — swap the Anthropic API for a self-hosted model using Ollama or vLLM running on your own GPU. The architecture supports all of this without redesign."

---

## SLIDE 16 — Key Takeaways

**VISUAL:**
> Five bullet points with icons:
> 🧠 RAG = right pages + right model = right answer
> 🔐 Keycloak SSO = enterprise auth without custom code
> 📚 Notebooks = isolated context per topic, like NotebookLM
> 📁 Google Drive ingestion = zero new workflow for your team
> 📋 Audit log = accountability + continuous improvement

**SCRIPT:**
"Five things to remember. RAG isn't magic — it's a retrieval pipeline. The quality of your chunking and your documents determines the quality of your answers. Keycloak gives you enterprise authentication for free, open source. Notebooks give you context isolation exactly like NotebookLM. Google Drive integration means your team doesn't change how they work. And the audit log is what turns a tool into a system. All the code from today is linked below."

---

## SLIDE 17 — Resources & Links

**VISUAL:**
> Clean slide with:
> 📦 GitHub repo: [link]
> 🛠️ Tech used:
> - Streamlit · ChromaDB · Keycloak · nginx · Claude claude-sonnet-4-6
> - Python · Docker · SQLite · Google Drive API
> 💬 Questions? Comments? → drop them below
> 🔔 Subscribe for Part 2: Self-hosted model + OpenShift deployment

**SCRIPT:**
"Everything is on GitHub — the full working code, the docker-compose, the realm export, the start script. Drop your questions in the comments — I read all of them. If you want to see Part 2 where we swap Claude for a self-hosted model and deploy this to OpenShift, hit subscribe. Thanks for watching The AI Stackk — see you in the next one."

---

## SLIDE 18 — End Card

**VISUAL:**
> The AI Stackk branding
> "Next episode → Self-Hosted RAG on OpenShift"
> Subscribe button prompt
> Social handles

---

# Slide Design Notes for Claude Design

Use these when creating slides in Claude Design (Canva):

**Color palette:**
- Background: `#0D1117` (dark) or `#FFFFFF` (light version)
- Accent: `#FF4B4B` (Streamlit red) for highlights
- Secondary: `#6C63FF` (purple) for AI/Claude references
- Text: `#E6EDF3` on dark / `#1C1E21` on light

**Typography:**
- Headlines: Bold, 48–60pt
- Body/script: Regular, 18–22pt
- Code blocks: Monospace (Fira Code or JetBrains Mono), 14pt

**Layout rules:**
- Max 6 bullet points per slide
- Every concept slide has a visual (diagram, code, or screenshot)
- Diagrams use simple boxes + arrows — no clip art
- Architecture slides: dark background with colored boxes

**Slide count:** 18 slides total (~75 seconds per slide at medium pace)
