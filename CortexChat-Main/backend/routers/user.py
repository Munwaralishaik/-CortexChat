"""
backend/routers/user.py — User Profile and Preferences Endpoints.

This module manages the endpoints for fetching and updating user-specific settings.
Because preferences (like theme, language) are isolated into a `UserPreferences`
table, these endpoints can be safely called frequently by the frontend without 
risking unintended modifications to core security fields in the `User` table.
"""

import os
import shutil
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.core.dependencies import get_current_user
from backend.database import get_db
from backend.models.user import User, UserPreferences

settings = get_settings()
router = APIRouter(prefix="/user", tags=["User"])

class PreferencesUpdate(BaseModel):
    language:         str | None = None
    theme:            str | None = None
    summary_mode:     str | None = None
    auto_delete_docs: bool | None = None


from backend.utils.security import verify_password, hash_password

class ProfileUpdate(BaseModel):
    name:             str | None = None
    gender:           str | None = None
    profession:       str | None = None
    current_password: str | None = None
    new_password:     str | None = None

from backend.models.chat import Chat
from backend.models.file import UploadedFile

@router.get("/profile")
async def get_profile(
    current_user: User        = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Return the authenticated user's profile and saved preferences."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.preferences))
        .where(User.id == current_user.id)
    )
    user = result.scalar_one_or_none()

    prefs = user.preferences
    return {
        "id":         user.id,
        "email":      user.email,
        "name":       user.name,
        "gender":     user.gender,
        "profession": user.profession,
        "created_at": user.created_at.isoformat(),
        "preferences": {
            "language":         prefs.language         if prefs else "English",
            "theme":            prefs.theme            if prefs else "dark",
            "summary_mode":     prefs.summary_mode     if prefs else "short",
            "auto_delete_docs": prefs.auto_delete_docs if prefs else False,
        },
    }

@router.get("/init")
async def get_dashboard_init(
    current_user: User        = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Combined endpoint to fetch everything needed for dashboard init in one round-trip."""
    # Fetch User + Prefs
    user_result = await db.execute(
        select(User).options(selectinload(User.preferences)).where(User.id == current_user.id)
    )
    user = user_result.scalar_one()

    # Fetch Chats (limit to 50 for performance as recommended)
    chats_result = await db.execute(
        select(Chat)
        .where(Chat.user_id == current_user.id)
        .order_by(Chat.updated_at.desc())
        .limit(50)
    )
    chats = chats_result.scalars().all()

    # Fetch Files
    files_result = await db.execute(
        select(UploadedFile).where(UploadedFile.user_id == current_user.id).order_by(UploadedFile.created_at.desc())
    )
    files = files_result.scalars().all()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "gender": user.gender,
            "profession": user.profession,
            "preferences": {
                "theme": user.preferences.theme if user.preferences else "dark",
                "language": user.preferences.language if user.preferences else "English",
                "summary_mode": user.preferences.summary_mode if user.preferences else "short",
                "auto_delete_docs": user.preferences.auto_delete_docs if user.preferences else False,
            }
        },
        "chats": [{"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat(), "is_archived": c.is_archived, "is_hidden": c.is_hidden} for c in chats],
        "files": [{"id": f.id, "original_name": f.original_name, "chat_id": f.chat_id, "file_type": f.file_type} for f in files]
    }

@router.patch("/profile")
async def update_profile(
    body:         ProfileUpdate,
    current_user: User            = Depends(get_current_user),
    db:           AsyncSession    = Depends(get_db),
):
    """Update user profile info (name, gender, password)."""
    result = await db.execute(
        select(User).where(User.id == current_user.id)
    )
    user = result.scalar_one_or_none()

    if body.name is not None:
        user.name = body.name
    if body.gender is not None:
        user.gender = body.gender
    if body.profession is not None:
        user.profession = body.profession

    if body.new_password:
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid current password.")
        user.password_hash = hash_password(body.new_password)

    await db.commit()
    await db.refresh(user)

    return {
        "id":         user.id,
        "email":  user.email,
        "name":   user.name,
        "gender": user.gender,
        "profession": user.profession,
    }


@router.patch("/preferences")
async def update_preferences(
    body:         PreferencesUpdate,
    current_user: User            = Depends(get_current_user),
    db:           AsyncSession    = Depends(get_db),
):
    """Update one or more user preference fields."""
    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()

    if prefs is None:
        # Create default preferences if missing
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)

    if body.language is not None:
        prefs.language = body.language
    if body.theme is not None:
        prefs.theme = body.theme
    if body.summary_mode is not None:
        prefs.summary_mode = body.summary_mode
    if body.auto_delete_docs is not None:
        prefs.auto_delete_docs = body.auto_delete_docs

    await db.commit()
    await db.refresh(prefs)

    return {
        "language":         prefs.language,
        "theme":            prefs.theme,
        "summary_mode":     prefs.summary_mode,
        "auto_delete_docs": prefs.auto_delete_docs,
    }
@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_account(
    current_user: User        = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Permanently delete user account and all associated data."""
    # 1. Delete physical files and indices
    user_dir = os.path.join(settings.upload_dir, str(current_user.id))
    if os.path.exists(user_dir):
        # shutil.rmtree removes the directory and all its contents
        shutil.rmtree(user_dir)

    # 2. Delete user from DB (Cascades will handle related records if configured, 
    # but let's be explicit if needed. The model has ForeignKey(..., ondelete="CASCADE"))
    await db.delete(current_user)
    await db.commit()

    return None
