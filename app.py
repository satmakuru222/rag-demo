import os
import streamlit as st
from dotenv import load_dotenv
from anthropic import Anthropic
from auth import require_auth, logout
from db import (init_db, upsert_user, log_query, log_feedback,
                get_audit_log, get_indexed_docs, log_indexed_doc)
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

# ── Helpers ───────────────────────────────────────────────────────────────────
COLORS = ["🔵", "🟢", "🟠", "🟣", "🔴", "🟡"]

def doc_color(doc_name: str, doc_list: list) -> str:
    idx = doc_list.index(doc_name) if doc_name in doc_list else 0
    return COLORS[idx % len(COLORS)]

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
    st.metric("Total chunks", stats["total_chunks"])
    st.metric("Documents", len(stats["documents"]))

    if stats["documents"]:
        st.divider()
        st.markdown("**Loaded documents:**")
        for i, doc in enumerate(stats["documents"]):
            st.markdown(f"{COLORS[i % len(COLORS)]} {doc}")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_labels = ["💬 Ask", "📄 Upload", "📊 Audit Log"] if is_admin else ["💬 Ask", "📄 Upload"]
tabs = st.tabs(tab_labels)

# ═══════════════════════════════════════════════════════════════
# TAB 1: Ask
# ═══════════════════════════════════════════════════════════════
with tabs[0]:
    st.header("Ask anything across your documents")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Replay history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
        if msg["role"] == "assistant":
            if msg.get("sources"):
                with st.expander("📌 Source chunks used"):
                    for src in msg["sources"]:
                        color = doc_color(src["doc"], stats["documents"])
                        st.info(f"{color} **{src['doc']}**\n\n{src['text']}")
            qid = msg.get("query_id")
            if qid:
                c1, c2, _ = st.columns([1, 1, 8])
                if c1.button("👍", key=f"up_{qid}"):
                    log_feedback(qid, user["id"], 1)
                    st.toast("Thanks for the feedback!")
                if c2.button("👎", key=f"dn_{qid}"):
                    log_feedback(qid, user["id"], -1)
                    st.toast("Noted — we'll improve.")

    question = st.chat_input("Ask a question across all your documents...")

    if question:
        if stats["total_chunks"] == 0:
            st.warning("No documents indexed yet. Go to the Upload tab first.")
        else:
            with st.chat_message("user"):
                st.markdown(question)
            st.session_state.chat_history.append({"role": "user", "content": question})

            sources = vs_query(question, n=4)

            with st.expander("📌 Retrieved chunks (what Claude is reading)", expanded=True):
                for src in sources:
                    color = doc_color(src["doc"], stats["documents"])
                    st.info(f"{color} **From: {src['doc']}**\n\n{src['text']}")

            context = "\n\n---\n\n".join(
                f"[From: {s['doc']}]\n{s['text']}" for s in sources
            )
            system_prompt = (
                "You are a helpful research assistant for The AI Stackk. "
                "Answer using ONLY the document context below. "
                "Cite which document each fact comes from by its filename. "
                "Use plain English. If the answer isn't in the context say: "
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

# ═══════════════════════════════════════════════════════════════
# TAB 2: Upload
# ═══════════════════════════════════════════════════════════════
with tabs[1]:
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
                    st.write(f"  → {added} chunks added")
                status.update(label="✅ Indexing complete!", state="complete")
            st.rerun()

    docs = get_indexed_docs()
    if docs:
        st.divider()
        st.subheader("All indexed documents")
        st.dataframe(
            [{
                "Document": d["filename"],
                "Source": d["source_type"],
                "Chunks": d["chunk_count"],
                "Uploaded by": d["uploaded_by"],
                "Indexed at": d["indexed_at"][:19],
            } for d in docs],
            use_container_width=True,
        )

    if not docs:
        st.info("No documents indexed yet. Upload your first PDF above!")
        st.markdown("""
**Try the sample doc:** `sample-docs/rag-explained.pdf`

**Then ask:**
- *"What is RAG in plain English?"*
- *"When should I NOT use RAG?"*
- *"Give me a real-world example."*
        """)

# ═══════════════════════════════════════════════════════════════
# TAB 3: Audit Log (admin only)
# ═══════════════════════════════════════════════════════════════
if is_admin:
    with tabs[2]:
        st.header("Audit Log")
        st.caption("All queries across all users — last 100.")

        rows = get_audit_log(limit=100)
        if rows:
            st.dataframe(
                [{
                    "User": r["email"] or r["user_id"],
                    "Question": r["question"][:80] + ("..." if len(r["question"]) > 80 else ""),
                    "Rating": "👍" if r["rating"] == 1 else ("👎" if r["rating"] == -1 else "—"),
                    "Time": r["ts"][:19],
                } for r in rows],
                use_container_width=True,
            )
        else:
            st.info("No queries logged yet.")
