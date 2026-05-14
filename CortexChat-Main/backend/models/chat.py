"""
backend/models/chat.py — Chat session and Message ORM models.

This module defines the SQLAlchemy 2.0 ORM models for conversational interactions.
A `Chat` represents a logical grouping of messages, analogous to a "chat thread" or "session".
Each `Chat` is owned by exactly one `User` and can contain multiple `Message` objects
and `UploadedFile` objects associated with that specific session context.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

# TYPE_CHECKING is False at runtime. We use this pattern to declare type hints
# for SQLAlchemy relationships without introducing circular import errors during module load.
if TYPE_CHECKING:
    from backend.models.user import User          # noqa: F401
    from backend.models.file import UploadedFile  # noqa: F401


class Chat(Base):
    """
    Represents a conversational session thread.

    Attributes:
        id: Primary key, auto-incremented integer.
        user_id: Foreign key linking to the `app_users` table.
        title: User-facing name of the chat (e.g., "Resume Review").
        is_archived: Soft-delete/archival flag for hiding chats from the active sidebar.
        is_hidden: Internal flag to hide the chat from normal UI lists.
        created_at: Automatically populated timestamp of creation.
        updated_at: Automatically updated timestamp whenever the row is modified.

    Relationships:
        user: The owner of this chat.
        messages: A chronologically ordered list of `Message` models in this chat.
                  Automatically deleted if the Chat is deleted (`cascade="all, delete-orphan"`).
        uploaded_files: Any files uploaded specifically within the context of this chat.
    """

    __tablename__ = "app_chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="New Chat")
    is_archived: Mapped[bool] = mapped_column(default=False, index=True)
    is_hidden: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), index=True
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="chats")
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="chat", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    uploaded_files: Mapped[list[UploadedFile]] = relationship(
        "UploadedFile", back_populates="chat", cascade="all, delete-orphan"
    )


class Message(Base):
    """
    Represents a single turn (utterance) within a chat.

    Attributes:
        id: Primary key, auto-incremented integer.
        chat_id: Foreign key linking to the parent `app_chats` row.
        role: Enum-like string identifying the sender. Usually 'user' or 'assistant'.
        content: The actual text payload of the message (can be markdown).
        created_at: Timestamp of when the message was sent.

    Relationships:
        chat: Back-reference to the parent Chat session.
    """

    __tablename__ = "app_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    chat_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("app_chats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # Expected: 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")
