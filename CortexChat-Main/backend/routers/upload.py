"""
backend/routers/upload.py — Document Ingestion and Indexing Endpoints.

This module handles the multipart-form upload process for user documents.
It acts as the entry point for the Retrieval-Augmented Generation (RAG) pipeline:
1. Receives and saves physical files to disk securely.
2. Triggers text extraction (`extract_text`).
3. Triggers vector embedding generation (`build_faiss_index`).
4. Persists the resulting filesystem paths to the `UploadedFile` database model.
"""

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.core.dependencies import get_current_user
from backend.database import get_db
from backend.models.file import UploadedFile
from backend.models.user import User
from backend.services.document_parser import extract_text
from backend.services.rag_pipeline import build_faiss_index
from backend.utils.file_validator import validate_upload

settings = get_settings()
router   = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/document", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file:    UploadFile = File(...),
    chat_id: int | None = Form(None),
    current_user: User  = Depends(get_current_user),
    db:      AsyncSession = Depends(get_db),
):
    """
    Upload, parse, and index a document for RAG.

    Steps:
    1. Validate file type and size.
    2. Save the file with a UUID filename.
    3. Extract text via the document parser.
    4. Build FAISS index for the document.
    5. Persist metadata to the database.
    """
    # ─── Validate ────────────────────────────────────────────────────────────
    ext = await validate_upload(file)

    # ─── Save file ───────────────────────────────────────────────────────────
    file_uuid   = str(uuid.uuid4())
    stored_name = f"{file_uuid}.{ext}"
    user_dir    = os.path.join(settings.upload_dir, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    file_path   = os.path.join(user_dir, stored_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # ─── Extract text ────────────────────────────────────────────────────────
    extracted_text = extract_text(content, ext)

    # ─── Build FAISS index ───────────────────────────────────────────────────
    index_path = os.path.join(user_dir, file_uuid)
    try:
        if extracted_text.strip():
            build_faiss_index(extracted_text, index_path)
        else:
            index_path = None
    except Exception as exc:
        print(f"[Upload] FAISS indexing failed: {exc}")
        index_path = None

    # ─── Persist to DB ───────────────────────────────────────────────────────
    db_file = UploadedFile(
        user_id=current_user.id,
        chat_id=chat_id,
        original_name=file.filename or stored_name,
        stored_name=stored_name,
        file_type=ext,
        file_size=len(content),
        extracted_text=extracted_text[:500000] if extracted_text else None,
        faiss_index_path=index_path,
    )
    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)

    return {
        "id":            db_file.id,
        "original_name": db_file.original_name,
        "file_type":     db_file.file_type,
        "file_size":     db_file.file_size,
        "indexed":       db_file.faiss_index_path is not None,
        "created_at":    db_file.created_at.isoformat(),
    }


@router.get("/files")
async def list_files(
    current_user: User        = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Return all files uploaded by the current user."""
    result = await db.execute(
        select(UploadedFile)
        .where(UploadedFile.user_id == current_user.id)
        .order_by(UploadedFile.created_at.desc())
    )
    files = result.scalars().all()

    return [
        {
            "id":            f.id,
            "original_name": f.original_name,
            "file_type":     f.file_type,
            "file_size":     f.file_size,
            "chat_id":       f.chat_id,
            "indexed":       f.faiss_index_path is not None,
            "created_at":    f.created_at.isoformat(),
        }
        for f in files
    ]


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id:      int,
    current_user: User        = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Delete a file record and its stored data."""
    result = await db.execute(
        select(UploadedFile).where(
            UploadedFile.id == file_id,
            UploadedFile.user_id == current_user.id,
        )
    )
    db_file = result.scalar_one_or_none()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found.")

    # Remove physical file and indices
    user_dir = os.path.join(settings.upload_dir, str(current_user.id))
    
    # 1. Original file
    file_path = os.path.join(user_dir, db_file.stored_name)
    if os.path.exists(file_path):
        os.remove(file_path)

    # 2. FAISS index and chunks (if indexed)
    if db_file.faiss_index_path:
        # faiss_index_path is the prefix (e.g., uploads/2/uuid)
        f_idx = db_file.faiss_index_path + ".faiss"
        f_chk = db_file.faiss_index_path + ".chunks"
        if os.path.exists(f_idx): os.remove(f_idx)
        if os.path.exists(f_chk): os.remove(f_chk)

    await db.delete(db_file)
    await db.commit()
