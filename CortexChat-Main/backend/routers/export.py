"""
backend/routers/export.py — PDF Export Endpoints.

This module provides functionality to generate downloadable artifacts from user data.
Currently, it supports compiling an active or archived chat thread into a styled, 
printable PDF document using ReportLab.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies import get_current_user
from backend.database import get_db
from backend.models.chat import Chat
from backend.models.user import User
from backend.services.export_service import generate_chat_pdf

router = APIRouter(prefix="/export", tags=["Export"])


class ExportPDFRequest(BaseModel):
    chat_id: int
    messages: list[dict] | None = None
    filename: str | None = None


@router.post("/pdf")
async def export_pdf(
    body:         ExportPDFRequest,
    current_user: User            = Depends(get_current_user),
    db:           AsyncSession    = Depends(get_db),
):
    """
    Generate a styled PDF of the requested chat (optionally just selected messages) 
    and return it as a download.
    """
    result = await db.execute(
        select(Chat)
        .where(Chat.id == body.chat_id, Chat.user_id == current_user.id)
    )
    chat = result.scalar_one_or_none()

    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found.")

    # Use provided messages if present, otherwise fetch all from chat
    if body.messages is not None:
        messages = body.messages
    else:
        # Fetch all messages from the DB
        result_msg = await db.execute(
            select(Chat).options(selectinload(Chat.messages)).where(Chat.id == body.chat_id)
        )
        full_chat = result_msg.scalar_one()
        messages = [
            {"role": m.role, "content": m.content}
            for m in full_chat.messages
        ]

    pdf_bytes = generate_chat_pdf(chat.title, messages)

    filename = body.filename or f"docuchat_{chat.id}.pdf"
    if not filename.endswith(".pdf"):
        filename += ".pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
