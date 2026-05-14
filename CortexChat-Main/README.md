# CortexChat — AI-Powered Document Intelligence Platform

> **Upload. Chat. Summarize. Export.**  
> A professional, full-stack RAG (Retrieval-Augmented Generation) platform built with a high-performance FastAPI backend and a sleek, modern Vanilla JS dashboard.

**🌐 Live Demo:** [https://CortexChat-jy9z.onrender.com](https://CortexChat-jy9z.onrender.com)

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688)](https://fastapi.tiangolo.com/)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.1-orange)](https://groq.com/)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-Inference_API-ffd21e)](https://huggingface.co/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🚀 Overview

CortexChat is a production-ready document interaction platform that allows users to "talk" to their data. Unlike standard chatbots, CortexChat uses **Retrieval-Augmented Generation (RAG)** to ground AI responses in the specific context of your uploaded files, ensuring high accuracy and reducing hallucinations.

It is designed to be **lightweight and fast** by leveraging Serverless Inference APIs (Groq & HuggingFace), eliminating the need for expensive local GPUs or multi-gigabyte model downloads.

---

## ✨ Key Features

- **Multi-Format Support**: Seamlessly parse **PDF, DOCX, TXT**, and even **Images (PNG/JPG)** via Tesseract OCR.
- **Ultra-Fast Chat**: Powered by **Groq (Llama 3.1)** for near-instant response times.
- **Contextual Intelligence**: Uses **FAISS** for efficient vector similarity search to find the exact paragraph you need.
- **Zero-Lag Dashboard**: A premium, state-synced UI with persistent document selection and flicker-free navigation.
- **Professional Security**: Secure OTP-based email verification, JWT session management, and encrypted password hashing.
- **Smart Summarization**: One-click multi-mode summarization (Brief, Detailed, or Bullet Points).
- **Export to PDF**: Generate high-quality, formatted PDF reports of your chat history.
- **Auto-Cleanup**: Privacy-focused document management with automated file cleanup.

---

## 🧠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Vanilla JS (ES Modules), CSS3 (Modern Glassmorphism), HTML5 |
| **Backend** | Python 3.12+, FastAPI (Asynchronous), Pydantic v2 |
| **Database** | PostgreSQL (Supabase) or SQLite with **SQLAlchemy 2.0 (Async)** |
| **AI (Chat)** | **Groq API** (Llama-3.1-8B-Instant) |
| **AI (Vector)** | **HuggingFace Inference API** (all-MiniLM-L6-v2) |
| **Vector DB** | **FAISS** (Facebook AI Similarity Search) |
| **Parsing** | PyMuPDF (PDF), python-docx (Word), Pytesseract (OCR) |
| **Security** | PyJWT, Passlib (Bcrypt), aiosmtplib (Async SMTP) |

---

## 📂 Project Structure

```text
CortexChat/
├── frontend/
│   ├── pages/
│   │   ├── index.html          # Landing / Login page
│   │   ├── signup.html         # Signup page
│   │   ├── verify.html         # OTP verification
│   │   ├── dashboard.html      # Main chat dashboard
│   │   ├── forgot_password.html# Password recovery start
│   │   └── reset_password.html # New password entry
│   ├── css/
│   │   ├── global.css          # Shared design system & CSS variables
│   │   ├── auth.css            # Auth pages styles
│   │   └── dashboard.css       # Dashboard layout & components
│   └── js/
│       ├── api.js              # Centralised API calls + JWT injection
│       ├── auth.js             # Auth flow logic (login/signup/verify)
│       ├── dashboard.js        # Dashboard state & orchestration
│       ├── upload.js           # File upload & grid controller
│       ├── sidebar.js          # Chat history & navigation
│       └── export.js           # PDF export trigger
│
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Settings & env vars (pydantic-settings)
│   ├── database.py             # Async SQLAlchemy engine & session
│   ├── models/
│   │   ├── user.py             # User, OTP, Preferences ORM
│   │   ├── chat.py             # Chat & Message ORM
│   │   └── file.py             # UploadedFile ORM
│   ├── routers/
│   │   ├── auth.py             # /auth/* endpoints
│   │   ├── chat.py             # /chat/* endpoints
│   │   ├── upload.py           # /upload/* endpoints
│   │   ├── export.py           # /export/* endpoints
│   │   └── user.py             # /user/* endpoints
│   ├── services/
│   │   ├── ai_engine.py        # Groq/HF Inference wrappers
│   │   ├── rag_pipeline.py     # RAG: Embed + FAISS + Generate
│   │   ├── document_parser.py  # PDF/DOCX/TXT/Image extraction
│   │   ├── otp_service.py      # OTP generation & SMTP email
│   │   └── export_service.py   # ReportLab PDF export
│   ├── utils/
│   │   ├── security.py         # JWT & Password hashing
│   │   ├── file_validator.py   # Type & size validation
│   │   └── chunker.py          # Text splitting for vectorization
│   └── core/
│       └── dependencies.py     # get_current_user() auth dependency
│
├── uploads/                    # Stored user files + FAISS indexes
├── .env                        # Local secrets (not committed)
├── .env.example                # Environment variable template
├── .python-version             # Python version specification
├── .gitignore                  # Ignore local files   
├── ARCHITECTURE.md             # System design & RAG pipeline docs 
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Multi-container orchestration
└── nginx.conf                  # Production reverse proxy config
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- Python 3.10 or higher
- [Tesseract OCR](https://tesseract-ocr.github.io/tessdoc/Installation.html) (optional, for image support)
- A Groq API Key ([Free here](https://console.groq.com/keys))
- A HuggingFace Token ([Free here](https://huggingface.co/settings/tokens))

### 2. Clone & Environment
```bash
git clone https://github.com/Munwar shaik/CortexChat.git
cd CortexChat

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory based on `.env.example`:
```env
# API Keys
GROQ_API_KEY=your_groq_key
HF_API_KEY=your_huggingface_key

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname

# Email (for OTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_USER=your@email.com
EMAIL_PASS=your_app_password
```

### 4. Run Locally
```bash
uvicorn backend.main:app --reload --port 8000
```
Visit `http://localhost:8000` in your browser.

---

## 🚀 Deployment

The application is designed to be easily deployed to platforms like **Railway, Render, or AWS**.

**Production Command**:
```bash
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 🤝 Contact

Developed by **Munwar Shaik**.
