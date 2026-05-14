# CortexChat — System Architecture Guide

## Overview

CortexChat is a high-performance RAG (Retrieval-Augmented Generation) platform designed for professional document intelligence. It allows users to upload large documents (up to 50MB) and interact with them using a hybrid AI architecture that combines **Groq's LPU™ technology** for near-instant reasoning with **HuggingFace's Inference API** for robust vector embeddings.

The system is built on a **Service-Oriented Architecture (SOA)** using FastAPI, ensuring asynchronous non-blocking operations for all file parsing and AI inference tasks.

---

## Architecture Diagram

```text
┌────────────────────────────────────────────────────────────────────┐
│                        BROWSER (Frontend)                          │
│                                                                    │
│     ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐     │
│     │ index    │  │ signup   │  │ verify   │  │  dashboard   │     │
│     │ .html    │  │ .html    │  │ .html    │  │  .html       │     │
│     └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬──────┘     │
│          └─────────────┴─────────────┴────────────────┘            │
│                                │ api.js (relative fetch + JWT)     │
└────────────────────────────────┼───────────────────────────────────┘
                                 │ HTTP/REST (JSON)
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend                            │
│                                                                    │
│   ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌────────┐  ┌────────┐   │
│   │ /auth   │  │ /chat   │  │ /upload  │  │/export │  │ /user  │   │
│   │ router  │  │ router  │  │ router   │  │ router │  │ router │   │
│   └────┬────┘  └────┬────┘  └────┬─────┘  └───┬────┘  └───┬────┘   │    
│        └────────────┴────────────┴────────────┴───────────┘        │
│                                │                                   │
│                      ┌─────────┴──────────┐                        │
│                      │   Services Layer   │                        │
│            ┌─────────┴────────────────────┴─────────┐              │
│            ▼                                        ▼              │
│    ┌──────────────┐                  ┌────────────────────────┐    │
│    │  ai_engine   │                  │      rag_pipeline      │    │
│    │ (Model Route)│                  │ (FAISS + Embed + Q&A)  │    │
│    └──────┬───────┘                  └──────────────┬─────────┘    │
│           │                                         │              │
└───────────┼─────────────────────────────────────────┼──────────────┘
            │                                         │
     ┌──────┴───────────────┐               ┌─────────┴─────────────┐
     │       Groq API       │               │ HuggingFace API (HF)  │
     │  (LPU Inference)     │               │ (Serverless Inference)│
     │ ┌──────────────────┐ │               │ ┌──────────────────┐  │
     │ │ Llama-3.3-70B    │ │               │ │ all-MiniLM-L6-v2 │  │
     │ │ (Synthesis/Sum)  │ │               │ │ (Embeddings)     │  │
     │ ├──────────────────┤ │               │ ├──────────────────┤  │
     │ │ Llama-3.1-8B     │ │               │ │ BART-Large-CNN   │  │
     │ │ (Q&A / Map)      │ │               │ │ (Sum Fallback)   │  │
     │ └──────────────────┘ │               │ └──────────────────┘  │
     └──────────────────────┘               └───────────────────────┘
              │                                         │
     ┌────────┴───────────────┐             ┌───────────┴───────────┐
     │   SQLite / PostgreSQL  │             │   Local FAISS Index   │
     │  (Users, Chats, Msgs)  │             │   + .chunks storage   │
     └────────────────────────┘             └───────────────────────┘
```

---

## RAG Pipeline — Detailed Flow

### Phase 1: Document Indexing (Upload Time)

1.  **Validation**: `file_validator.py` checks MIME type and confirms the file is under **50MB**.
2.  **Parsing**: `document_parser.py` extracts raw text based on extension (PDF, DOCX, TXT, or OCR for Images).
3.  **Chunking**: `chunker.py` splits text into overlapping 500-word blocks.
4.  **Embedding**: Chunks are sent in batches of 32 to **HF Inference API** (`all-MiniLM-L6-v2`) to generate 384-dimensional vectors.
5.  **Vector Store**: Vectors are added to a **FAISS IndexFlatIP** (Inner Product for Cosine Similarity).
6.  **Persistence**: The `.faiss` index and `.chunks` text file are saved to `uploads/{user_id}/`.

### Phase 2: Question Answering (Query Time)

1.  **Context Retrieval**:
    *   User query is embedded via HF API.
    *   FAISS performs a similarity search to find the **Top-8** most relevant chunks.
    *   Retrieved chunks are formatted into a single context block.
2.  **Prompt Engineering**:
    *   A professional system prompt is constructed, injecting the retrieved context and conversation history.
3.  **Groq Inference**:
    *   The request is routed through the **Groq API** using an automated model-rotation strategy (Llama 3.3 70B → Llama 3.1 8B → Fallbacks).
    *   Streaming responses are yielded word-by-word via **Server-Sent Events (SSE)** or standard JSON.

### Phase 3: Summarization (Map-Reduce)

1.  **Map Phase**: The document is split into 4000-character segments. Each segment is summarized into key highlights using `llama-3.1-8b-instant`.
2.  **Fallback**: If Groq rate limits are hit, the system silently switches to **HF BART-Large-CNN** for individual segments.
3.  **Reduce Phase**: All highlights are aggregated and passed to `llama-3.3-70b-versatile` to synthesize a cohesive final summary in the requested mode (Brief, Detailed, etc.).

---

## Database Schema

CortexChat uses a relational schema (SQLAlchemy) supporting both SQLite (Dev) and PostgreSQL (Prod):

-   **Users**: Identity, email verification status, and timestamps.
-   **OTPRecords**: Temporary 6-digit codes for passwordless auth.
-   **UserPreferences**: Per-user settings (Language, Theme, Summary Mode).
-   **Chats**: Conversation containers linked to a specific user.
-   **Messages**: Individual role-based messages ('user' | 'assistant') with Markdown content.
-   **UploadedFiles**: Metadata for parsed documents, including paths to their local FAISS indexes.

---

## API Reference

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| **POST** | `/auth/send-otp` | ✗ | Trigger async SMTP email with 6-digit code. |
| **POST** | `/auth/verify-otp` | ✗ | Exchange OTP for a 24h JWT access token. |
| **POST** | `/upload/document`| ✓ | Multipart upload. Triggers parsing & FAISS indexing. |
| **GET**  | `/upload/files`   | ✓ | Fetch metadata for all documents in current session. |
| **POST** | `/chat/message`   | ✓ | Primary RAG endpoint. Supports `stream=true`. |
| **GET**  | `/chat/history`   | ✓ | Retrieve list of previous conversation titles. |
| **POST** | `/export/pdf`     | ✓ | Generates a ReportLab PDF from chat JSON. |
| **GET**  | `/user/profile`   | ✓ | Returns active user data and UI preferences. |

---

## Security Practices

1. **Passwordless Auth**: OTP-only flow minimizes the attack surface for credential stuffing.
2. **Stateless JWT**: Tokens are signed with `HS256` and stored in `localStorage` with auto-injection into headers.
3. **Strict Validation**: Files are checked for magic-byte headers and a hard **50MB limit** before reaching the parser.
4. **Isolated Storage**: Each user's documents and FAISS indexes are stored in unique, UUID-named subdirectories.
5. **ORM Safety**: All database interactions use SQLAlchemy 2.0's parameterized async queries to prevent SQLi.
6. **Rate Limiting**: AI inference calls are wrapped in robust error handling to manage provider-level throttling gracefully.

---

## Frontend Logic & SPA Architecture

CortexChat uses a **Vanilla JS Single-Page Application (SPA)** architecture. This ensures high performance and zero framework overhead.

-   **State Management**: `dashboard.js` maintains the active state (current `chat_id`, `file_id`, and `history`) in memory. 
-   **API Client**: `api.js` acts as a centralized fetch wrapper that automatically injects JWT tokens into the `Authorization` header and handles global error states (like 401 Unauthorized).
-   **Component Logic**:
    -   `sidebar.js`: Manages real-time filtering of chat history and file lists.
    -   `upload.js`: Handles drag-and-drop events and chunked upload monitoring.
    -   `chat.js`: Uses a custom Markdown renderer to transform AI responses into formatted blocks (code, bold, lists).
-   **Theme Engine**: The UI uses a system of **CSS Variables** defined in `global.css`, allowing for instant switching between light/dark modes and enabling the signature "glassmorphism" aesthetic.

---

## DevOps & Persistence Layout

In production (Docker), the system maintains a strict separation between code and state using volumes:

```text
/app/
├── backend/ (Code)
├── frontend/ (Code)
└── data/ (Persistent Volume)
    ├── CortexChat.db           # SQLite Database
    ├── uploads/              # Per-user document storage
    │   └── {user_id}/
    │       ├── {uuid}.pdf    # Raw original file
    │       ├── {uuid}.faiss  # Vector index
    │       └── {uuid}.chunks # Raw text chunks
    └── logs/                 # System and error logs
```

---

## Model Resilience Strategy

The `ai_engine.py` implements a **fail-safe inference chain**:

1.  **Primary Attempt**: Request is sent to the top-tier Groq model (e.g., Llama 3.3 70B).
2.  **Tier-2 Rotation**: If a `429` (Rate Limit) or `503` is received, the engine automatically cycles to the next model in the `GROQ_MODELS` list (Llama 3.1 8B, Qwen, etc.).
3.  **HF Fallback**: For summarization, if all Groq models are exhausted, the system falls back to the **HuggingFace BART** model to ensure the user still receives an answer.
4.  **Graceful Degradation**: If the network is entirely down, the UI renders a cached error message with instructions to wait for the rate-limit window to reset.

---

## AI Engine Model Strategy

The `ai_engine.py` module manages an aggressive **Token-Limit Rotation** to maximize free-tier availability:

| Task | Primary Model | Provider |
| :--- | :--- | :--- |
| **Chat / Q&A** | `llama-3.1-8b-instant` | Groq |
| **Summarization** | `llama-3.3-70b-versatile` | Groq |
| **Embeddings** | `all-MiniLM-L6-v2` | HuggingFace |
| **Fallback Sum** | `bart-large-cnn` | HuggingFace |

**Rotation Order**: `meta-llama/llama-4-scout` → `qwen3-32b` → `llama-3.3-70b` → `llama-3.1-8b`.

---

## Technical Stack

*   **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2.
*   **Security**: PyJWT (HS256), Passlib (Bcrypt), Async SMTP (aiosmtplib).
*   **Vector Engine**: FAISS-cpu (local index math), NumPy.
*   **Parsing**: PyMuPDF, python-docx, Pytesseract OCR.
*   **Frontend**: Vanilla JS (ES Modules), Modern CSS Variables, HTML5.
*   **Infrastructure**: Docker, Docker Compose, Nginx (Reverse Proxy).

---

## Future Improvements

*   **[Medium] Streaming SSE**: Fully implement word-by-word streaming in the UI for smoother UX.
*   **[High] Multi-Document Context**: Allow querying across multiple selected documents simultaneously.
*   **[Low] PostgreSQL Migration**: Full Supabase integration for highly scalable production clusters.
*   **[Medium] Semantic Caching**: Cache common questions to reduce API costs and latency.
*   **[Low] Dark Mode Sync**: OS-level theme detection and synchronization.

---

## Technical Appendix: Core Modules

### 1. Asynchronous Task Processing
To maintain a responsive UI, CortexChat leverages FastAPI's `BackgroundTasks` for heavy computations:
-   **Summarization**: When a user uploads a 50MB file, the text extraction and Map-Reduce synthesis run in an isolated async thread.
-   **Email Delivery**: OTP delivery is non-blocking; the API returns a success message immediately while the SMTP handshake completes in the background.

### 2. Document Parsing & OCR Logic
The `document_parser.py` follows a "Best-Effort" extraction strategy:
1.  **Digital Extraction**: Attempts to pull metadata and text streams using `PyMuPDF`.
2.  **Layout Analysis**: For `.docx`, it preserves basic heading structures to improve chunking context.
3.  **OCR Fallback**: If a PDF contains no selectable text (scanned image), the system automatically triggers **Tesseract OCR** to digitize the content before passing it to the RAG pipeline.

### 3. Environmental Bridge (`config.py`)
The system follows "12-Factor App" principles. `backend/config.py` acts as a central authority:
-   **Validation**: Uses Pydantic-style checks to ensure `GROQ_API_KEY` is present before the app starts.
-   **Dynamic Limits**: `MAX_FILE_SIZE_MB` and `JWT_EXPIRY` can be adjusted without changing code, simply by updating the `.env` file and restarting the container.

### 4. Logging & Diagnostics
Structured logging is enabled across all service layers:
-   **Audit Logs**: Tracks user uploads and AI interactions (anonymized).
-   **Error Tracking**: Detailed tracebacks are captured in `data/logs/error.log` for troubleshooting Docker deployment issues.
