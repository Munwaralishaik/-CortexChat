"""
backend/services/rag_pipeline.py — Retrieval-Augmented Generation (RAG) Engine.

This module orchestrates the vectorization and similarity search phases of DocuChat.

How RAG Works in DocuChat:
  1. INDEXING (Upload Time):
     - The document text is split into semantic chunks.
     - Each chunk is embedded using the HuggingFace Inference API
       (model: sentence-transformers/all-MiniLM-L6-v2, yielding 384-dim vectors).
     - These vectors are persisted locally via a FAISS index (fast, on-device math).

  2. RETRIEVAL (Query Time):
     - The user's question is embedded using the exact same MiniLM model.
     - FAISS computes cosine similarity to find the top-k most relevant text chunks.
     - Those chunks form the strict "context window" passed to the LLM.

  3. GENERATION:
     - The `ai_engine.py` module uses the context to formulate a grounded answer.
"""

import os
import numpy as np
import faiss
from huggingface_hub import InferenceClient

from backend.utils.chunker import chunk_text
from backend.services.ai_engine import generate_answer, generate_answer_stream, summarize, summarize_stream
from backend.config import get_settings

settings = get_settings()

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM   = 384   # all-MiniLM-L6-v2 output dimension


# ─── Embedding via HF API ─────────────────────────────────────────────────────

def _get_client() -> InferenceClient:
    if not settings.hf_api_key:
        raise RuntimeError(
            "HF_API_KEY is not set. Add it to your .env file. "
            "Get a free key at https://huggingface.co/settings/tokens"
        )
    return InferenceClient(token=settings.hf_api_key)


def _embed(texts: list[str]) -> np.ndarray:
    """
    Embed a list of texts using the HF Inference API.

    Returns:
        Float32 numpy array of shape (len(texts), EMBEDDING_DIM).
    """
    try:
        client = _get_client()
        # feature_extraction returns a list[list[float]] or list[list[list[float]]]
        # For sentence-transformers models it returns shape [n_texts, dim]
        raw = client.feature_extraction(texts, model=EMBEDDING_MODEL)
        
        if isinstance(raw, dict) and "error" in raw:
            raise RuntimeError(f"HF API Error: {raw['error']}")
            
        arr = np.array(raw, dtype=np.float32)

        # Some HF endpoints return [n, 1, dim] — squeeze the middle dim if present
        if arr.ndim == 3:
            arr = arr[:, 0, :]
        return arr
    except Exception as exc:
        print(f"[RAG] Embedding failed: {exc}")
        # Return zero vector fallback to prevent complete crash
        return np.zeros((len(texts), EMBEDDING_DIM), dtype=np.float32)


# ─── Indexing ─────────────────────────────────────────────────────────────────

def build_faiss_index(text: str, index_path: str) -> None:
    """
    Chunk document text, embed chunks via HF API, and save FAISS index to disk.

    Args:
        text:       Full extracted document text.
        index_path: File path prefix (without extension) for saving index + chunks.
    """
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    if not chunks:
        raise ValueError("Document has no extractable text to index.")

    print(f"[RAG] Embedding {len(chunks)} chunks via HF API…")

    # Embed in small batches to respect API limits
    BATCH = 32
    embeddings_list = []
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i : i + BATCH]
        embeddings_list.append(_embed(batch))
    embeddings = np.vstack(embeddings_list).astype(np.float32)

    # Normalise for cosine similarity via inner product
    faiss.normalize_L2(embeddings)

    # Build FAISS index
    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(embeddings)

    # Persist index + raw chunks
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    faiss.write_index(index, index_path + ".faiss")
    with open(index_path + ".chunks", "w", encoding="utf-8") as f:
        f.write("\n<<<CHUNK>>>\n".join(chunks))

    print(f"[RAG] Indexed {len(chunks)} chunks → {index_path}")


# ─── Retrieval ────────────────────────────────────────────────────────────────

def retrieve_relevant_chunks(query: str, index_path: str, top_k: int = 4) -> list[str]:
    """
    Find the top-k most relevant chunks for a query using FAISS.

    Args:
        query:      The user's question.
        index_path: File path prefix used when building the index.
        top_k:      Number of chunks to retrieve.

    Returns:
        List of relevant text chunk strings.
    """
    faiss_file  = index_path + ".faiss"
    chunks_file = index_path + ".chunks"

    if not os.path.exists(faiss_file):
        return []

    index = faiss.read_index(faiss_file)
    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks = f.read().split("\n<<<CHUNK>>>\n")

    # Embed the query (single text → shape [1, dim])
    query_vec = _embed([query])
    faiss.normalize_L2(query_vec)

    k = min(top_k, index.ntotal)
    _, indices = index.search(query_vec, k)

    # Retrieve chunks with neighboring context for better continuity
    results = []
    seen_indices = set()
    for i in indices[0]:
        if i >= len(chunks) or i < 0:
            continue
        # Add the match and its immediate neighbors (one before, one after)
        # This helps "complete" sections and provides better flow.
        for offset in [-1, 0, 1]:
            idx = i + offset
            if 0 <= idx < len(chunks) and idx not in seen_indices:
                results.append(chunks[idx])
                seen_indices.add(idx)
                
    return results[:top_k * 2] # Limit to avoid overwhelming the model


# ─── Query Entry Points ───────────────────────────────────────────────────────

def answer_question(
    question: str,
    index_path: str,
    language: str = "English",
    history: list[dict] | None = None,
) -> str:
    """Full RAG pipeline: embed query → retrieve chunks → generate answer."""
    # Robust greeting detection
    greetings = ["hello", "hi", "hey", "hola", "greetings", "how are you", "good morning", "good afternoon", "good evening", "what's up", "sup", "howdy"]
    clean_q = question.lower().strip().replace("?", "").replace("!", "")
    
    # Check if the query is a simple greeting or very short
    is_social = any(clean_q == g or clean_q.startswith(g + " ") for g in greetings) or len(clean_q) < 3
    
    if is_social:
        return generate_answer(question, context="", language=language, history=history, doc_active=True)

    chunks  = retrieve_relevant_chunks(question, index_path, top_k=8)
    context = "\n\n".join(chunks) if chunks else ""
    return generate_answer(question, context, language=language, history=history, doc_active=True)


def answer_question_stream(
    question: str,
    index_path: str,
    language: str = "English",
    history: list[dict] | None = None,
):
    """Full RAG pipeline (streaming version)."""
    # Robust greeting detection
    greetings = ["hello", "hi", "hey", "hola", "greetings", "how are you", "good morning", "good afternoon", "good evening", "what's up", "sup", "howdy"]
    clean_q = question.lower().strip().replace("?", "").replace("!", "")
    is_social = any(clean_q == g or clean_q.startswith(g + " ") for g in greetings) or len(clean_q) < 3
    
    if is_social:
        yield from generate_answer_stream(question, context="", language=language, history=history, doc_active=True)
        return

    chunks  = retrieve_relevant_chunks(question, index_path, top_k=8)
    context = "\n\n".join(chunks) if chunks else ""
    yield from generate_answer_stream(question, context, language=language, history=history, doc_active=True)


def summarize_document(
    index_path: str,
    mode: str = "short",
    language: str = "English",
) -> str:
    """Summarize a document using its stored indexed chunks."""
    chunks_file = index_path + ".chunks"
    if not os.path.exists(chunks_file):
        return "No indexed document found. Please upload a document first."

    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks = f.read().split("\n<<<CHUNK>>>\n")

    # Use up to 5,000 chunks (covers millions of characters)
    text = " ".join(chunks[:5000])
    return summarize(text, mode=mode, language=language)
def summarize_document_stream(
    index_path: str,
    mode: str = "short",
    language: str = "English",
):
    """Generator version of summarize_document."""
    chunks_file = index_path + ".chunks"
    if not os.path.exists(chunks_file):
        yield "No indexed document found. Please upload a document first."
        return

    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks = f.read().split("\n<<<CHUNK>>>\n")

    text = " ".join(chunks[:5000])
    for part in summarize_stream(text, mode=mode, language=language):
        yield part


async def process_summary_background(
    message_id: int,
    index_path: str,
    mode: str,
    language: str,
    chat_id: int = None,
    user_prompt: str = None,
    file_name: str = None
):
    """
    Async background task to process a long summary and update the database record.
    This bypasses HTTP timeouts entirely. Has full error recovery to prevent stuck spinners.
    """
    from backend.database import AsyncSessionLocal
    from backend.models.chat import Message
    from sqlalchemy import update, select
    import asyncio

    async def _save_to_db(content: str):
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Message)
                    .where(Message.id == message_id)
                    .values(content=content)
                )
                await db.commit()
        except Exception as e:
            print(f"[BG] DB save failed: {e}")

    try:
        # 1. Prepare text
        chunks_file = index_path + ".chunks"
        if not os.path.exists(chunks_file):
            await _save_to_db("No indexed document found. Please re-upload the document.")
            return

        with open(chunks_file, "r", encoding="utf-8") as f:
            chunks = f.read().split("\n<<<CHUNK>>>\n")
        text = " ".join(chunks[:5000])

        # 2. Process in a loop — save partial results to DB as each section is done
        full_summary = ""
        for part in summarize_stream(text, mode=mode, language=language):
            full_summary += part
            await _save_to_db(full_summary)
            await asyncio.sleep(0.1)

        # 3. Final save (ensure we write even if no parts were yielded)
        if not full_summary:
            full_summary = "Summary generation failed. The AI service may be temporarily unavailable. Please try again."
            await _save_to_db(full_summary)

        # 4. Post-response Titling
        if chat_id and user_prompt and full_summary and "failed" not in full_summary:
            from backend.database import AsyncSessionLocal
            from backend.models.chat import Chat
            from backend.services.ai_engine import generate_title
            
            try:
                async with AsyncSessionLocal() as db:
                    chat_res = await db.execute(
                        select(Chat).where(Chat.id == chat_id)
                    )
                    chat = chat_res.scalar_one_or_none()
                    if chat:
                        title_clean = (chat.title or "").strip().lower()
                        if title_clean in ("new chat", "new conversation", ""):
                            chat.title = generate_title(user_prompt, assistant_reply=full_summary, file_name=file_name)
                            await db.commit()
            except Exception as title_err:
                print(f"[BG] Title generation failed: {title_err}")

    except Exception as e:
        print(f"[BG] Background summary crashed: {e}")
        # CRITICAL: Always write an error to DB so the spinner resolves
        error_msg = (
            f"**Summary generation failed.**\n\n"
            f"**Reason:** {str(e)[:200]}\n\n"
            f"This is usually caused by hitting the Groq free-tier daily limit (100,000 tokens/day).\n"
            f"Please wait a few hours and try again."
        )
        await _save_to_db(error_msg)
