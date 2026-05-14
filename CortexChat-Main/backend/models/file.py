"""
backend/models/file.py — UploadedFile ORM model.

This module defines the SQLAlchemy 2.0 ORM model for file uploads.
It manages the metadata for documents uploaded by users, acting as the bridge
between the raw physical files on disk, the extracted text in the database, 
and the localized FAISS vector embeddings used in the Retrieval-Augmented Generation (RAG) pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

# TYPE_CHECKING is False at runtime. Used to prevent circular imports 
# while still providing type hinting for SQLAlchemy relationships.
if TYPE_CHECKING:
    from backend.models.user import User  # noqa: F401
    from backend.models.chat import Chat  # noqa: F401


class UploadedFile(Base):
    """
    Represents metadata and system paths for a user-uploaded document.

    Attributes:
        id: Primary key, auto-incremented integer.
        user_id: Foreign key linking to the `app_users` table (the document owner).
        chat_id: Optional foreign key. If null, the file is globally accessible to the user.
                 If set, the file is strictly scoped to a specific chat session.
        original_name: The actual filename provided by the user (e.g., "tax_return_2025.pdf").
        stored_name: An obfuscated UUID-based filename used securely on the filesystem.
        file_type: Extension or type identifier (e.g., "pdf", "docx", "txt").
        file_size: The size of the file in bytes.
        extracted_text: The raw, parsed text content extracted from the document via PyMuPDF/OCR.
        faiss_index_path: Absolute or relative path to the persistent `.index` file containing 
                          the HuggingFace vector embeddings for this document.
        created_at: Timestamp of when the file was uploaded to the system.

    Relationships:
        user: Back-reference to the owner.
        chat: Optional back-reference to a specific chat scope.
    """

    __tablename__ = "app_uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chat_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("app_chats.id", ondelete="CASCADE"), nullable=True, index=True
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)  # UUID-based filename
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)     # pdf|docx|txt|png|jpg
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)        # bytes
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    faiss_index_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="uploaded_files")
    chat: Mapped[Chat | None] = relationship("Chat", back_populates="uploaded_files")
