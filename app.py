import os
import asyncio
import streamlit as st
from dotenv import load_dotenv

def _suppress_connection_reset(loop, context):
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError):
        return
    loop.default_exception_handler(context)

try:
    asyncio.get_event_loop().set_exception_handler(_suppress_connection_reset)
except RuntimeError:
    pass

from anthropic import Anthropic
from auth import require_auth, logout
from db import (
    init_db, upsert_user, log_query, log_feedback, get_audit_log,
    get_indexed_docs, log_indexed_doc, delete_indexed_doc,
    get_notebooks, create_notebook, delete_notebook, rename_notebook,
)
from vectorstore import add_document, query as vs_query, get_stats, delete_document, delete_notebook_collection
from ingest.processor import extract_text, chunk_text

load_dotenv()
init_db()

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

# ── Sidebar — Notebook picker ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"👤 **{user['name']}**")
    st.caption(user["email"])
    if is_admin:
        st.caption("🛡️ Admin")
    if st.button("Sign out"):
        logout()

    st.divider()
    st.markdown("### 📚 My Notebooks")

    notebooks = get_notebooks(user["id"])

    with st.popover("➕ New notebook", use_container_width=True):
        new_name = st.text_input("Notebook name", placeholder="e.g. Red Hat Docs", key="new_nb_name")
        if st.button("Create", key="create_nb"):
            name = new_name.strip()
            if name and st.session_state.get("_last_nb_created") != name:
                st.session_state["_last_nb_created"] = name
                nb_id = create_notebook(name, user["id"])
                st.session_state["active_notebook"] = nb_id
                st.session_state.pop("chat_history", None)
                st.rerun()

    if not notebooks:
        st.caption("No notebooks yet — create one above.")
        st.session_state.pop("active_notebook", None)
    else:
        active_id = st.session_state.get("active_notebook", notebooks[0]["id"])
        for nb in notebooks:
            is_active = nb["id"] == active_id
            col1, col2 = st.columns([5, 1])
            label = f"{'▶ ' if is_active else ''}{nb['name']}"
            if col1.button(label, key=f"nb_{nb['id']}",
                           help=f"{nb['doc_count']} doc(s) · {nb['chunk_count']} chunks",
                           use_container_width=True,
                           type="primary" if is_active else "secondary"):
                st.session_state["active_notebook"] = nb["id"]
                st.session_state.pop("chat_history", None)
                st.rerun()
            if col2.button("🗑️", key=f"del_nb_{nb['id']}", help="Delete notebook"):
                delete_notebook_collection(nb["id"])
                delete_notebook(nb["id"], user["id"])
                if st.session_state.get("active_notebook") == nb["id"]:
                    st.session_state.pop("active_notebook", None)
                st.session_state.pop("chat_history", None)
                st.rerun()
        st.session_state["active_notebook"] = active_id

# ── Require a notebook ────────────────────────────────────────────────────────
active_notebook_id = st.session_state.get("active_notebook")

if not active_notebook_id:
    st.title("🧠 RAG Platform — The AI Stackk")
    st.info("👈 Create a notebook in the sidebar to get started.")
    if is_admin:
        rows = get_audit_log(limit=100)
        if rows:
            st.subheader("📊 Audit Log")
            st.dataframe(
                [{"Notebook": r.get("notebook_name", "—"),
                  "User": r["email"] or r["user_id"],
                  "Question": r["question"][:80],
                  "Rating": "👍" if r["rating"] == 1 else ("👎" if r["rating"] == -1 else "—"),
                  "Time": r["ts"][:19]} for r in rows],
                use_container_width=True,
            )
    st.stop()

active_nb = next((n for n in get_notebooks(user["id"]) if n["id"] == active_notebook_id), None)
nb_name = active_nb["name"] if active_nb else "Notebook"
stats = get_stats(active_notebook_id)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_labels = ["💬 Ask", "📄 Sources", "📊 Audit Log"] if is_admin else ["💬 Ask", "📄 Sources"]
tabs = st.tabs(tab_labels)

# ═══════════════════════════════════════════════════════════════
# TAB 1: Ask
# ═══════════════════════════════════════════════════════════════
with tabs[0]:
    st.header(f"💬 {nb_name}")

    if stats["total_chunks"] == 0:
        st.info("No documents in this notebook yet. Go to the **Sources** tab to upload PDFs.")
    else:
        st.caption(f"{stats['total_chunks']} chunks across {len(stats['documents'])} document(s)")

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

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

        question = st.chat_input("Ask a question across your documents...")

        if question:
            with st.chat_message("user"):
                st.markdown(question)
            st.session_state.chat_history.append({"role": "user", "content": question})

            sources = vs_query(active_notebook_id, question, n=4)

            with st.expander("📌 Retrieved chunks", expanded=True):
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

            query_id = log_query(user["id"], active_notebook_id, question, sources, full_response)
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": full_response,
                "sources": sources,
                "query_id": query_id,
            })
            st.rerun()

# ═══════════════════════════════════════════════════════════════
# TAB 2: Sources
# ═══════════════════════════════════════════════════════════════
with tabs[1]:
    st.header(f"📄 Sources — {nb_name}")

    uploaded_files = st.file_uploader(
        "Upload PDFs to this notebook",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"uploader_{active_notebook_id}",
    )

    if uploaded_files:
        indexed_names = {d["filename"] for d in get_indexed_docs(active_notebook_id)}
        new_files = [f for f in uploaded_files if f.name not in indexed_names]
        if not new_files:
            st.info("All uploaded files are already indexed in this notebook.")
        else:
            with st.status(f"Indexing {len(new_files)} new document(s)...", expanded=True) as status:
                for f in new_files:
                    st.write(f"Processing **{f.name}**...")
                    text = extract_text(f.read())
                    chunks = chunk_text(text)
                    added = add_document(active_notebook_id, f.name, chunks)
                    log_indexed_doc(active_notebook_id, f.name, "upload", user["email"], added)
                    st.write(f"  → {added} chunks added")
                status.update(label="✅ Indexing complete!", state="complete")
            st.rerun()

    st.divider()
    docs = get_indexed_docs(active_notebook_id)
    if docs:
        st.subheader("Indexed sources")
        for doc in docs:
            col1, col2, col3 = st.columns([5, 2, 1])
            col1.markdown(f"**{doc['filename']}**")
            col2.caption(f"{doc['chunk_count']} chunks · {doc['indexed_at'][:10]}")
            if col3.button("🗑️", key=f"del_doc_{doc['id']}", help="Remove from notebook"):
                delete_document(active_notebook_id, doc["filename"])
                delete_indexed_doc(active_notebook_id, doc["filename"])
                st.toast(f"Removed {doc['filename']}")
                st.rerun()
    else:
        st.info("No sources yet. Upload PDFs above to start asking questions.")

# ═══════════════════════════════════════════════════════════════
# TAB 3: Audit Log (admin only)
# ═══════════════════════════════════════════════════════════════
if is_admin:
    with tabs[2]:
        st.header("📊 Audit Log")
        st.caption("All queries across all users and notebooks — last 100.")
        rows = get_audit_log(limit=100)
        if rows:
            st.dataframe(
                [{
                    "Notebook": r.get("notebook_name", "—"),
                    "User": r["email"] or r["user_id"],
                    "Question": r["question"][:80] + ("..." if len(r["question"]) > 80 else ""),
                    "Rating": "👍" if r["rating"] == 1 else ("👎" if r["rating"] == -1 else "—"),
                    "Time": r["ts"][:19],
                } for r in rows],
                use_container_width=True,
            )
        else:
            st.info("No queries logged yet.")
