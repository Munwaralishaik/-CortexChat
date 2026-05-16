import random
import string
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.user import OTPRecord

settings = get_settings()

OTP_EXPIRY_MINUTES = 10
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


async def generate_and_store_otp(email: str, db: AsyncSession, context: str = "signup") -> str:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.execute(
        delete(OTPRecord).where(
            (OTPRecord.email == email) | (OTPRecord.expires_at < now)
        )
    )

    otp_code = _generate_otp()
    expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)

    record = OTPRecord(
        email=email,
        otp_code=otp_code,
        is_used=False,
        expires_at=expires_at,
    )

    db.add(record)
    await db.commit()

    await _send_otp_email(email, otp_code, context)

    return otp_code


async def verify_otp(email: str, code: str, db: AsyncSession) -> bool:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    result = await db.execute(
        select(OTPRecord).where(
            OTPRecord.email == email,
            OTPRecord.otp_code == code,
        )
    )

    record = result.scalar_one_or_none()

    if not record:
        return False

    is_valid = record.expires_at > now

    await db.delete(record)
    await db.commit()

    return is_valid


async def _send_otp_email(to_email: str, otp_code: str, context: str):
    if context == "reset":
        subject = "CortexChat Password Reset OTP"
        title = "Password Reset OTP"
    else:
        subject = "CortexChat Verification OTP"
        title = "Verify Your CortexChat Account"

    plain_body = f"""
{title}

Your OTP Code is: {otp_code}

This OTP expires in {OTP_EXPIRY_MINUTES} minutes.

- CortexChat Team
"""

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: auto; padding: 24px;">
        <h2>{title}</h2>
        <p>Your OTP code is:</p>
        <h1 style="letter-spacing: 8px;">{otp_code}</h1>
        <p>This OTP expires in {OTP_EXPIRY_MINUTES} minutes.</p>
        <p>- CortexChat Team</p>
    </div>
    """

    payload = {
        "sender": {
            "name": "CortexChat",
            "email": settings.email_user,
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": plain_body,
        "htmlContent": html_body,
    }

    headers = {
        "api-key": settings.brevo_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(BREVO_API_URL, json=payload, headers=headers)

    if response.status_code not in (200, 201):
        raise RuntimeError(f"Brevo API error {response.status_code}: {response.text}")

    print(f"OTP sent successfully to {to_email} via Brevo API")