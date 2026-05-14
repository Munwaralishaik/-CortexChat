"""
backend/services/ai_engine.py — Core AI Inference & Provider Routing.

Architecture (Three-Model Routing by Task):
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ Task                    │ Provider   │ Model                             │
  ├─────────────────────────┼────────────┼───────────────────────────────────┤
  │ Q&A / Chat              │ Groq API   │ llama-3.1-8b-instant   (6k TPM)   │
  │ Map phase (per-chunk)   │ Groq API   │ llama-3.1-8b-instant   (6k TPM)   │
  │ Summary synthesis       │ Groq API   │ llama-3.3-70b-versatile (6k TPM)  │
  │ Map-phase fallback      │ HuggingFace│ facebook/bart-large-cnn           │
  │ Embeddings (RAG)        │ HuggingFace│ sentence-transformers/            │
  │                         │ Inference  │   all-MiniLM-L6-v2                │
  └──────────────────────────────────────────────────────────────────────────┘

Summarization Pipeline (Paragraph-aware Map-Reduce):
  1. MAP: Split document on paragraph boundaries into ~4000-char chunks. 
          Each chunk is sent to llama-3.1 to extract headings and short descriptions. 
          HF BART acts as a silent fallback for rate-limiting.
  2. REDUCE: All mini-summaries are joined and sent to llama-3.3-70b-versatile
             for final synthesis matching the requested tone/format.

Q&A Pipeline:
  - Top relevant FAISS chunks are retrieved as context (≤5000 chars).
  - llama-3.1-8b-instant answers, grounded strictly in the document context.
  - If no document is provided, the model answers from its general training data.

API keys (free tiers):nt
             fallback if Groq is busy.
  2. REDUCE — All mini-summaries are joined and sent to llama-3.3-70b-versatile
              for final synthesis in the requested mode (short / detailed /
              bullet / executive / study_notes).

Q&A Pipeline:
  - Top relevant FAISS chunks are retrieved and passed as context (≤5000 chars).
  - llama-3.1-8b-instant answers grounded in the document context.
  - If the topic is not in the document, the model answers from general knowledge.

API keys (free tiers):
  Groq  → https://console.groq.com/keys          (add GROQ_API_KEY to .env)
  HF    → https://huggingface.co/settings/tokens  (add HF_API_KEY to .env)
"""

from __future__ import annotations

import time

# pyrefly: ignore [missing-import]
from groq import Groq
from huggingface_hub import InferenceClient

from backend.config import get_settings

settings = get_settings()

# ─── Model identifiers ────────────────────────────────────────────────────────
# Groq Models — each has its OWN independent daily token limit.
# By rotating through all of them we get effectively unlimited capacity.
# Rotation order: best → cheapest → fallback
GROQ_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",  # Llama 4 — separate limit
    "qwen/qwen3-32b",                              # Qwen3 32B — separate limit
    "openai/gpt-oss-20b",                          # GPT-OSS 20B — separate limit
    "openai/gpt-oss-120b",                         # GPT-OSS 120B — separate limit
    "llama-3.3-70b-versatile",                     # Llama 3.3 70B — may be exhausted
    "llama-3.1-8b-instant",                        # Llama 3.1 8B — fallback
]
# Primary models for quality tasks (rotated automatically if exhausted)
GROQ_SUM_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_CHAT_MODEL  = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_MINI_MODEL  = "meta-llama/llama-4-scout-17b-16e-instruct"
# HuggingFace BART — used as silent fallback for map phase.
HF_SUMMARY_MODEL = "facebook/bart-large-cnn"


# ─── Client factories ─────────────────────────────────────────────────────────

def _groq_client() -> Groq:
    """Return a configured Groq client."""
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys "
            "and add GROQ_API_KEY=gsk_... to your .env file."
        )
    return Groq(api_key=settings.groq_api_key, timeout=60.0, max_retries=2)


def _hf_client() -> InferenceClient:
    """Return a configured HuggingFace InferenceClient (embeddings + BART)."""
    if not settings.hf_api_key:
        raise RuntimeError(
            "HF_API_KEY is not set. Get a free key at https://huggingface.co/settings/tokens "
            "and add HF_API_KEY=hf_... to your .env file."
        )
    return InferenceClient(token=settings.hf_api_key, timeout=60.0)


# ─── Q&A / Chat (Groq → Llama 3.1) ──────────────────────────────────────────

def generate_answer(
    question: str,
    context: str,
    language: str = "English",
    history: list[dict] | None = None,
    doc_active: bool = False
) -> str:
    """
    Generate a standalone answer.
    """
    client = _groq_client()

    if context.strip():
        system_content = (
            f"You are an expert document assistant. \n"
            f"STRICT REQUIREMENT: You MUST respond ONLY in {language}. This is non-negotiable.\n"
            f"RULES:\n"
            f"1. **DEPTH FIRST**: exhaustive, in-depth answer.\n"
            f"2. **GROUNDED**: Base answers on DOCUMENT CONTEXT.\n"
            f"3. **FORMATTING**: Markdown only.\n"
            f"4. **DIRECT**: No preambles.\n"
            f"5. **NO EMOJIS**."
        )
        user_content = f"DOCUMENT CONTEXT:\n{context[:20000]}\n\nQUESTION: {question}"
    else:
        system_content = (
            f"You are a helpful AI assistant. \n"
            f"STRICT REQUIREMENT: You MUST respond ONLY in {language}. This is non-negotiable.\n"
            f"Do not use emojis. Use Markdown formatting. DO NOT wrap regular text in markdown code blocks unless you are writing actual programming code."
        )
        if not doc_active:
            system_content += (
                "\nIMPORTANT: No document is currently selected. "
                "Act purely as a general chatbot. "
                "If the user asks a general question, answer it normally. "
                "CRITICAL: If the user asks ANY question referring to 'the document', 'this file', or anything related to previously discussed documents, you MUST REJECT IT. "
                "You must say EXACTLY: 'No document is currently selected. Please choose a document from the sidebar to discuss.' "
                "DO NOT attempt to answer using conversation history."
            )
        else:
            system_content += (
                "\nCRITICAL RULE: The user is making a general statement or greeting. "
                "Acknowledge them naturally and briefly. "
                "DO NOT complain about missing documents, DO NOT ask them to select a document, and DO NOT mention summarization."
            )
        user_content = question

    messages = [{"role": "system", "content": system_content}]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": user_content})

    # Try every model in rotation — each has its own daily limit
    for model in GROQ_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2048,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            err_str = str(e)
            if "400" in err_str and "decommissioned" in err_str:
                continue  # Skip decommissioned models silently
            if "429" in err_str or "413" in err_str:
                print(f"[Chat] {model} rate-limited, trying next...")
                continue
            raise  # Unexpected error — surface it


def generate_answer_stream(
    question: str,
    context: str,
    language: str = "English",
    history: list[dict] | None = None,
    doc_active: bool = False
):
    """
    Generator that yields tokens in real-time.
    """
    client = _groq_client()

    if context.strip():
        system_content = (
            f"You are an expert document assistant. \n"
            f"STRICT REQUIREMENT: You MUST respond ONLY in {language}. This is non-negotiable.\n"
            f"RULES:\n"
            f"1. **DEPTH FIRST**: exhaustive, in-depth answer.\n"
            f"2. **GROUNDED**: Base answers on DOCUMENT CONTEXT.\n"
            f"3. **FORMATTING**: Use Markdown.\n"
            f"4. **DIRECT**: No preambles.\n"
            f"5. **NO EMOJIS**."
        )
        user_content = f"DOCUMENT CONTEXT:\n{context[:20000]}\n\nQUESTION: {question}"
    else:
        system_content = (
            f"You are a helpful AI assistant. \n"
            f"STRICT REQUIREMENT: You MUST respond ONLY in {language}. This is non-negotiable.\n"
            f"Do not use emojis. Use Markdown formatting. DO NOT wrap regular text in markdown code blocks unless you are writing actual programming code."
        )
        if not doc_active:
            system_content += (
                "\nIMPORTANT: No document is currently selected. "
                "Act purely as a general chatbot. "
                "If the user asks a general question, answer it normally. "
                "CRITICAL: If the user asks ANY question referring to 'the document', 'this file', or anything related to previously discussed documents, you MUST REJECT IT. "
                "You must say EXACTLY: 'No document is currently selected. Please choose a document from the sidebar to discuss.' "
                "DO NOT attempt to answer using conversation history."
            )
        else:
            system_content += (
                "\nCRITICAL RULE: The user is making a general statement or greeting. "
                "Acknowledge them naturally and briefly. "
                "DO NOT complain about missing documents, DO NOT ask them to select a document, and DO NOT mention summarization."
            )
        user_content = question

    clean_history = []
    if history:
        for msg in history[-10:]:
            content = msg["content"]
            if msg["role"] == "user" and "DOCUMENT CONTEXT:" in content:
                parts = content.split("QUESTION: ")
                if len(parts) > 1:
                    content = parts[-1]
            clean_history.append({"role": msg["role"], "content": content})

    messages = [{"role": "system", "content": system_content}]
    if clean_history:
        messages.extend(clean_history)
    messages.append({"role": "user", "content": user_content})

    for model in GROQ_MODELS:
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2048,
                temperature=0.3,
                stream=True,
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            return # Success
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "413" in err_str:
                print(f"[Chat] {model} rate-limited (stream), trying next...")
                continue
            print(f"[Chat] Stream error on {model}: {e}")
            break
    
    yield "[Error: All AI models are currently unavailable. Please try again later.]"

    return "All AI models are temporarily unavailable. Please try again in a few minutes."


# ─── Summarization ────────────────────────────────────────────────────────────

def summarize(
    text: str,
    mode: str = "short",
    language: str = "English",
) -> str:
    """Synchronous wrapper for the new streaming summarizer."""
    return "".join(list(summarize_stream(text, mode, language)))


def summarize_stream(
    text: str,
    mode: str = "short",
    language: str = "English",
):
    """
    Generator that yields summary parts. 
    Uses a strict token-budget refill strategy to avoid Groq Free Tier limits.
    """
    # Better splitting: try double newline, then single newline, then sentences.
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) < 5:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    # --- MAP PHASE ---
    # 3,500 chars ≈ 875 tokens input. With 8B 6k TPM, this is very safe.
    chunk_size_chars = 3500
    
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paragraphs:
        if current_len + len(para) > chunk_size_chars and current:
            chunks.append("\n\n".join(current))
            current, current_len = [], 0
        current.append(para)
        current_len += len(para)
    if current:
        chunks.append("\n\n".join(current))

    # Cap at 80 chunks max (~280k chars) to protect the 70B daily quota.
    chunks = chunks[:80]

    intermediate_summaries: list[str] = []
    use_hf_only = False # Flag to switch to HF if Groq hits rate limits
    
    for idx, chunk in enumerate(chunks):
        try:
            s = ""
            if not use_hf_only:
                # AGGRESSIVE FALLBACK: Try every model in rotation for this specific chunk
                for model_idx in range(len(GROQ_MODELS)):
                    current_model = GROQ_MODELS[(idx + model_idx) % len(GROQ_MODELS)]
                    
                    if idx > 0: time.sleep(5)
                    
                    try:
                        s = _groq_mini_summary(chunk, language, mode, model=current_model)
                        if s: break # Found a model that works for this chunk
                    except Exception as e:
                        if "413" in str(e) or "429" in str(e):
                            print(f"[AI] {current_model} rate limited, trying next...")
                            continue 
                        else: raise e
                
                if not s:
                    print(f"[AI] All models rate-limited for chunk {idx}. Using HF fallback.")
                    use_hf_only = True
            
            if not s:
                s = _hf_fast_summary(chunk[:4000])
                
            if s:
                intermediate_summaries.append(s)
        except Exception as e:
            print(f"[AI] Chunk {idx} map failed: {e}")

    # --- FINAL PHASE: One unified synthesis call for ALL modes ---
    # This produces a single, cohesive, non-truncated response.
    if not intermediate_summaries:
        yield "The document could not be summarized. Please check your API keys and connectivity."
        return

    # Join all section highlights into one big context.
    combined = "\n\n".join(intermediate_summaries)
    
    # Use the final synthesis function (tries all models in rotation)
    final_summary = _groq_summarize(combined[:32000], mode, language)
    yield final_summary


def _hf_fast_summary(text: str) -> str:
    """Use Hugging Face InferenceClient's summarization task."""
    try:
        client = _hf_client()
        # BART has a 1024 token limit (~3500 chars). We use 3000 to be safe.
        # Passing only text and model to ensure compatibility with all HF library versions
        result = client.summarization(
            text[:3000],
            model=HF_SUMMARY_MODEL
        )
        
        # result is typically a dict with 'summary_text' or a list containing such a dict
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("summary_text", "")
        if isinstance(result, dict):
            return result.get("summary_text", "")
        return str(result)
    except Exception as e:
        err_msg = str(e).lower()
        if "getaddrinfo" in err_msg or "connection" in err_msg:
            print(f"[HF] Network Error: Cannot reach HuggingFace. Check your internet/proxy settings.")
        else:
            print(f"[HF] Task failed: {e}")
    return ""


def _groq_mini_summary(text: str, language: str, mode: str = "short", model: str = GROQ_MINI_MODEL) -> str:
    """
    Map-phase: extract key-points from each document chunk.
    Outputs are compact so that ALL sections fit in the final synthesis call.
    """
    try:
        # Strict safety check: 12k chars ≈ 3k tokens input. Safe under 6k TPM.
        safe_text = text[:12000]

        # MAP PHASE prompt: compact key-point extraction for all modes.
        if mode in ("detailed", "study_notes"):
            system_msg = (
                f"You are an expert indexer. For each heading/section in the text, extract:\n"
                f"- The section name\n"
                f"- 3-5 compact technical bullet points covering key concepts, commands, and facts\n"
                f"Be dense and precise. Use **bold** for terms. Respond in {language}."
            )
            m_tokens = 700
        else:
            # Map phase for overview modes: extract a 'Table of Contents' with brief summaries
            system_msg = (
                f"You are an indexer. Extract the main topics and 1-sentence summary for each "
                f"from this document section. Respond in {language}."
            )
            m_tokens = 500

        client = _groq_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": safe_text}
            ],
            max_tokens=m_tokens,
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        err_msg = str(e).lower()
        if "getaddrinfo" in err_msg or "connection" in err_msg:
            print(f"[Mini] Network Error: Cannot reach Groq. Check your internet/proxy settings.")
        elif "timeout" in err_msg:
            print(f"[Mini] Request timed out.")
        else:
            print(f"[Mini] Error: {e}")
        return ""


def _groq_summarize(text: str, mode: str, language: str) -> str:
    """Final Reduce phase — synthesizes mini-summaries into the requested format."""
    client = _groq_client()

    if not text.strip():
        return "The document appears to be empty or unreadable."

    mode_instructions = {
        "short": "Write a concise 2-3 paragraph summary of the document's main purpose, key topics, and conclusions.",
        "detailed": (
            "Create a comprehensive technical overview of the entire document. "
            "Synthesize the content into clear, logical sections using meaningful headings and subheadings. "
            "Your goal is to provide a deep, professional understanding of the document's structure and core technical details "
            "without being a literal transcription of the index. "
            "\n"
            "Format using this structure:\n"
            "## [Major Technical Theme/Chapter Group]\n"
            "Provide a thorough high-level summary of this theme (3-4 sentences).\n"
            "\n"
            "### [Specific Topic/Sub-component]\n"
            "- **Technical Core**: Explain the primary technical concepts or architecture here.\n"
            "- **Key Procedures**: List important workflows, commands, or configuration steps.\n"
            "- **Critical Insights**: Mention specific constraints, parameters, or edge cases found in the document.\n"
            "\n"
            "STRICT RULES:\n"
            "- Be technical and precise. Use **bold** for all key terms and ```code``` for all syntax.\n"
            "- Ensure the flow is logical and the summary covers the breadth of the document from start to finish.\n"
            "- Focus on making the response clear and professional."
        ),
        "bullet": "Summarize into grouped bullet points. Use **bold** for key terms and ### headers for each major topic.",
        "executive": "Write a professional executive summary: a 1-paragraph overview, bold bullet points for key findings, and a Conclusion.",
        "study_notes": (
            "Transform the document into expert-level study notes for a student. "
            "Structure it logically by chapter. "
            "Format EXACTLY like this:\n"
            "## Topic / Chapter Name\n"
            "- **Concept Name**: Thorough technical explanation of this concept.\n"
            "- **Important Syntax/Command**: ```bash\ncommand here\n```\n"
            "- **Crucial Fact**: Why this matters or how it works internally.\n"
            "\n"
            "### Sub-topic Name\n"
            "- **Term**: Detailed definition including context and usage.\n"
            "- **Step-by-Step**: List any procedures or workflows in order.\n"
            "\n"
            "STRICT RULES:\n"
            "- Exhaustive coverage: Include every key term and technical detail.\n"
            "- Formatting: Use **bold** for terms and ```blocks``` for all code/commands.\n"
            "- Complete the full portion of the document assigned to you."
        ),
    }
    instruction = mode_instructions.get(mode, "Summarize the following document.")

    # Give detailed mode more token budget to avoid mid-document truncation
    max_tok = 5000 if mode in ("detailed", "study_notes") else 1500
    max_tok_fallback = 3000 if mode in ("detailed", "study_notes") else 900

    system_prompt = f"""You are a professional document analyst.

Your task: {instruction}

STRICT ARCHITECTURAL RULES:
1. **NO VERBATIM COPYING**: Never reproduce source sentences. Write fresh, high-level overviews.
2. **HEADING STRUCTURE**: You MUST use `##` for Chapters and `###` for Sub-sections. This is non-negotiable.
3. **FULL COVERAGE**: You are given an INDEX of the entire document. You must process EVERY section in that index.
4. **NO TRUNCATION**: Your response must be complete and cover the last section of the index.
5. **BULLETS ONLY**: Use concise bullet points for descriptions (max 20 words per bullet).

Respond in {language}. Use Markdown. No emojis."""

    # Single-pass synthesis for distillation modes (short/bullet/etc)
    # The input text (index) is now small enough to handle without splitting.
    try:
        input_tokens = len(text) // 4
        safe_max_tok = min(max_tok, 5800 - input_tokens)
        if safe_max_tok < 500: safe_max_tok = 500

        response = client.chat.completions.create(
            model=GROQ_SUM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"Document content:\n\n{text}"},
            ],
            max_tokens=int(safe_max_tok),
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Sum] {GROQ_SUM_MODEL} failed ({e}), falling back to {GROQ_CHAT_MODEL}")
        
        text_fallback = text[:8000]
        input_tokens_fb = len(text_fallback) // 4
        safe_max_fb = min(max_tok_fallback, 5800 - input_tokens_fb)
        
        response = client.chat.completions.create(
            model=GROQ_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"Document content:\n\n{text_fallback}"},
            ],
            max_tokens=int(safe_max_fb),
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()
            
    # Default single-pass synthesis for shorter indexes
    try:
        # Budgeting for single pass
        input_tokens = len(text) // 4
        safe_max_tok = min(max_tok, 5800 - input_tokens)
        if safe_max_tok < 500: safe_max_tok = 500

        response = client.chat.completions.create(
            model=GROQ_SUM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"Document content:\n\n{text}"},
            ],
            max_tokens=int(safe_max_tok),
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Sum] {GROQ_SUM_MODEL} failed ({e}), falling back to {GROQ_CHAT_MODEL}")
        
        text_fallback = text[:8000]
        input_tokens_fb = len(text_fallback) // 4
        safe_max_fb = min(max_tok_fallback, 5800 - input_tokens_fb)
        
        response = client.chat.completions.create(
            model=GROQ_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"Document content:\n\n{text_fallback}"},
            ],
            max_tokens=int(safe_max_fb),
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()


def _groq_translate(text: str, language: str) -> str:
    """Translate text to the target language using Groq."""
    client = _groq_client()
    response = client.chat.completions.create(
        model=GROQ_CHAT_MODEL,
        messages=[
            {"role": "system", "content": f"Translate the following text to {language}. Return only the translation."},
            {"role": "user",   "content": text},
        ],
        max_tokens=1500, # Increased for translations
        temperature=0.1,
    )
    return response.choices[0].message.content.strip()


def generate_title(user_message: str, assistant_reply: str = "", file_name: str = None) -> str:
    """
    Generate a very short (2-4 words) title for a conversation based on the first message and reply.
    """
    try:
        client = _groq_client()
        content_prompt = f"User: {user_message}\n"
        if file_name:
            content_prompt += f"Active Document: {file_name}\n"
        if assistant_reply:
            content_prompt += f"Assistant: {assistant_reply[:500]}\n"
            
        response = client.chat.completions.create(
            model=GROQ_CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional UX titling expert. Your ONLY purpose is to extract an ultra-concise 2-3 word "
                        "title summarizing the core topic of the conversation. Do NOT answer the user. Do NOT converse. "
                        "Make the titles sound modern, highly professional, and cool (e.g., 'Python Ecosystem', 'Conda Strategy', 'System Architecture'). "
                        "Base your title primarily on the provided Assistant response. "
                        "Return ONLY the title text. No quotes, no prefixes."
                    )
                },
                {"role": "user", "content": content_prompt},
            ],
            max_tokens=15,
            temperature=0.3,
        )
        title = response.choices[0].message.content.strip()
        # Aggressive cleanup
        for prefix in ["title:", "chat:", "conversation:", "subject:"]:
            if title.lower().startswith(prefix):
                title = title[len(prefix):].strip()
        return title.replace('"', '').replace("'", "").strip()
    except Exception:
        return user_message[:30].strip() + "..."
