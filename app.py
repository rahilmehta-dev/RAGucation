import io, re, time, uuid
from pathlib import Path
from typing import List, Dict

import streamlit as st
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
import ollama

DB_DIR = Path(".rag_db")
COLLECTION_NAME = "books_rag"
DEFAULT_MODEL = "llama3.1:8b-instruct"
EMBED_MODEL = "all-MiniLM-L6-v2"  # fast CPU embedder
DEFAULT_CHUNK = 900
DEFAULT_OVERLAP = 150
DEFAULT_TOPK = 5

# ------------------- CACHE LAYERS -------------------
@st.cache_resource(show_spinner=False)
def _embedder():
    return SentenceTransformer(EMBED_MODEL)

@st.cache_resource(show_spinner=False)
def _collection():
    client = chromadb.PersistentClient(path=str(DB_DIR), settings=Settings(allow_reset=True))
    return client.get_or_create_collection(name=COLLECTION_NAME)

# ------------------- HELPERS -------------------
def _chunk_text(text: str, size: int, overlap: int) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks, i = [], 0
    step = max(1, size - overlap)
    while i < len(text):
        chunks.append(text[i:i+size])
        i += step
    return chunks

def _extract_chunks_from_pdf(file_bytes: bytes, filename: str, size: int, overlap: int) -> List[Dict]:
    reader = PdfReader(io.BytesIO(file_bytes))
    out = []
    for p_idx, page in enumerate(reader.pages, start=1):
        txt = page.extract_text() or ""
        if len(txt) < 200:
            continue
        for ch in _chunk_text(txt, size=size, overlap=overlap):
            out.append({
                "id": str(uuid.uuid4()),
                "text": ch,
                "meta": {"source": filename, "page": p_idx}
            })
    return out

def ingest_files(files, size: int, overlap: int) -> int:
    if not files:
        st.warning("No PDFs selected.")
        return 0
    coll = _collection()
    embedder = _embedder()

    all_chunks = []
    for f in files:
        st.write(f"Reading **{f.name}** …")
        all_chunks.extend(_extract_chunks_from_pdf(f.read(), f.name, size=size, overlap=overlap))

    if not all_chunks:
        st.warning("No text extracted from uploaded PDFs.")
        return 0

    texts = [c["text"] for c in all_chunks]
    ids = [c["id"] for c in all_chunks]
    metas = [c["meta"] for c in all_chunks]

    st.write("Computing embeddings (CPU)…")
    embs = embedder.encode(texts, normalize_embeddings=True, convert_to_numpy=True).tolist()

    st.write("Writing to vector store …")
    coll.add(ids=ids, documents=texts, metadatas=metas, embeddings=embs)
    return len(ids)

def retrieve(query: str, k: int):
    embedder = _embedder()
    coll = _collection()
    qvec = embedder.encode([query], normalize_embeddings=True, convert_to_numpy=True).tolist()[0]
    res = coll.query(query_embeddings=[qvec], n_results=k, include=["documents", "metadatas", "distances"])
    if not res["documents"]:
        return []
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    dists = res["distances"][0]
    out = []
    for doc, meta, dist in zip(docs, metas, dists):
        out.append({"document": doc, "metadata": meta, "distance": float(dist)})
    return out

def build_messages(question: str, contexts: List[Dict]):
    sys = (
        "You are a careful tutor. Answer ONLY using the provided context. "
        "If the context is insufficient, say you don't know. "
        "Cite sources inline using [n] where n is the context index (keep page numbers from the context)."
    )
    ctx_lines = []
    for i, c in enumerate(contexts, 1):
        src = c["metadata"]["source"]
        page = c["metadata"]["page"]
        snippet = c["document"]
        # keep snippet short in the prompt to save tokens
        snippet = (snippet[:700] + "…") if len(snippet) > 700 else snippet
        ctx_lines.append(f"[{i}] ({src} p.{page}) {snippet}")

    user = (
        "CONTEXT:\n" + "\n\n".join(ctx_lines) +
        f"\n\nQUESTION: {question}\n"
        "INSTRUCTIONS: Use ONLY the context above. Cite like [1], [2]. If not covered, say you don't know."
    )
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]

def answer_with_ollama(model_name: str, messages: List[Dict]) -> str:
    resp = ollama.chat(model=model_name, messages=messages)
    return resp["message"]["content"]

# ------------------- UI -------------------
st.set_page_config(page_title="ScholarRAG — Textbook Q&A (Local)", page_icon="📚", layout="wide")
st.title("ScholarRAG — Textbook Q&A (Local, Offline)")

with st.sidebar:
    st.subheader("Library / Indexing")
    files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)
    chunk = st.slider("Chunk size", 400, 1600, DEFAULT_CHUNK, 50)
    overlap = st.slider("Chunk overlap", 0, 400, DEFAULT_OVERLAP, 10)
    if st.button("Index PDFs"):
        with st.spinner("Indexing…"):
            n = ingest_files(files, size=chunk, overlap=overlap)
        st.success(f"Indexed {n} chunks into local store.")

    st.divider()
    st.subheader("Settings")
    model = st.text_input("Ollama model", value=DEFAULT_MODEL, help="e.g., llama3.1:8b-instruct")
    topk = st.slider("Top-K passages", 1, 12, DEFAULT_TOPK, 1)

st.markdown("#### Ask from your textbooks")
question = st.text_input("Your question", placeholder="e.g., State and explain the spectral theorem.")
go = st.button("Retrieve & Answer")

if go and question.strip():
    t0 = time.time()

    with st.spinner("Retrieving relevant passages…"):
        ctx = retrieve(question, k=topk)

    if not ctx:
        st.warning("No passages found. Upload PDFs and run Index first.")
    else:
        st.markdown("##### Retrieved context")
        for i, c in enumerate(ctx, 1):
            meta = c["metadata"]
            short = c["document"][:400] + ("…" if len(c["document"]) > 400 else "")
            st.caption(f"[{i}] ({meta['source']} p.{meta['page']}) • score≈{1.0 - c['distance']:.3f}")
            st.write(short)

        with st.spinner("Generating answer…"):
            msgs = build_messages(question, ctx)
            try:
                out = answer_with_ollama(model, msgs)
            except Exception as e:
                st.error(f"Ollama error: {e}")
                out = None

        if out:
            latency_ms = int((time.time() - t0) * 1000)
            st.markdown("### Answer")
            st.write(out)
            st.markdown(f"**Latency:** {latency_ms} ms")