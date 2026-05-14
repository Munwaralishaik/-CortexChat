"""
backend/models/user.py — Identity and Preferences ORM models.

This module manages everything related to user identity, security verification,
and personal preferences within the system.

Authentication State Machine:
  1. SIGNUP: User registers -> DB Record Created (`is_active=False`) -> OTP generated/emailed.
  2. VERIFY: User inputs OTP -> System validates -> `is_active=True` -> JWT issued.
  3. LOGIN:  User provides Email/Password -> Hash validated -> JWT issued (OTP skipped).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

# TYPE_CHECKING is False at runtime. Prevents circular imports while 
# permitting static type checkers to accurately map SQLAlchemy relationships.
if TYPE_CHECKING:
    from backend.models.chat import Chat          # noqa: F401
    from backend.models.file import UploadedFile  # noqa: F401


class User(Base):
    """
    Represents a registered user identity in the system.

    Attributes:
        id: Primary key, auto-incremented integer.
        email: Unique email address used for login and verification.
        name: User's display name.
        gender: Optional demographic string ('male', 'female', 'other').
        profession: Optional string to personalize prompt instructions.
        password_hash: Irreversible bcrypt hash of the user's password.
        is_active: Boolean flag governing login capability. 
                   Set to False upon creation, True only after OTP verification.
        created_at: Timestamp of account registration.

    Relationships:
        chats: A list of all conversation threads owned by this user.
        uploaded_files: A list of all files uploaded by this user.
        preferences: A 1-to-1 relationship containing UI/UX configurations.
    """

    __tablename__ = "app_users"

    id:            Mapped[int]       = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    email:         Mapped[str]       = mapped_column(String(255), unique=True, nullable=False, index=True)
    name:          Mapped[str | None] = mapped_column(String(100), nullable=True)
    gender:        Mapped[str | None] = mapped_column(String(20), nullable=True) # 'male' | 'female' | 'other'
    profession:    Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)   # bcrypt hash
    is_active:     Mapped[bool]      = mapped_column(Boolean, default=False, index=True)         # True after OTP verify
    created_at:    Mapped[datetime]  = mapped_column(DateTime, server_default=func.now(), index=True)

    # Relationships
    chats: Mapped[list[Chat]] = relationship(
        "Chat", back_populates="user", cascade="all, delete-orphan"
    )
    uploaded_files: Mapped[list[UploadedFile]] = relationship(
        "UploadedFile", back_populates="user", cascade="all, delete-orphan"
    )
    preferences: Mapped[UserPreferences] = relationship(
        "UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class OTPRecord(Base):
    """
    Represents a transient verification code (One Time Password).
    
    Security mechanics:
    - OTPs are scoped strictly to an email address.
    - An OTP is strictly single-use (`is_used` toggles to True upon successful verification).
    - Hard expiry enforcement (`expires_at`) prevents replay or brute-force attacks.
    """

    __tablename__ = "app_otp_records"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    email:      Mapped[str]      = mapped_column(String(255), nullable=False, index=True)
    otp_code:   Mapped[str]      = mapped_column(String(6), nullable=False)
    is_used:    Mapped[bool]     = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class UserPreferences(Base):
    """
    Represents a 1-to-1 extension of the User table for application settings.

    These values are highly decoupled from security logic, allowing the UI 
    to fetch and mutate them continuously without risking state corruption 
    in the primary User identity table.
    """

    __tablename__ = "app_user_preferences"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id:      Mapped[int] = mapped_column(
        Integer, ForeignKey("app_users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    language:     Mapped[str] = mapped_column(String(20), default="English")
    theme:        Mapped[str] = mapped_column(String(10), default="dark")
    summary_mode:     Mapped[str]  = mapped_column(String(30), default="short")
    auto_delete_docs: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship("User", back_populates="preferences")
