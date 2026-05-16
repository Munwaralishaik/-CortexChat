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

    subject = "CortexChat OTP Verification"

    body = f"""
Your OTP Code is: {otp_code}

This OTP expires in 10 minutes.

- CortexChat Team
"""

    headers = {
        "accept": "application/json",
        "api-key": settings.brevo_api_key,
        "content-type": "application/json",
    }

    data = {
        "sender": {
            "name": "CortexChat",
            "email": settings.email_user
        },
        "to": [
            {
                "email": to_email
            }
        ],
        "subject": subject,
        "htmlContent": f"""
        <html>
            <body>
                <h2>Your OTP Code: {otp_code}</h2>
                <p>This OTP expires in 10 minutes.</p>
                <br>
                <p>- CortexChat Team</p>
            </body>
        </html>
        """
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers=headers,
            json=data
        )

    print(response.text)

    if response.status_code not in [200, 201]:
        raise Exception(f"Brevo email failed: {response.text}")

    print(f"OTP sent successfully to {to_email}")