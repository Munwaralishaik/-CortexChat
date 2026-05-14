import random
import string
from datetime import datetime, timedelta, timezone

import aiosmtplib
from email.mime.text import MIMEText
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

    if context == "reset":
        subject = "Password Reset OTP"
    else:
        subject = "DocuChat Verification OTP"

    body = f"""
Your OTP Code is: {otp_code}

This OTP expires in 10 minutes.

- DocuChat Team
"""

    message = MIMEText(body)
    message["From"] = settings.email_user
    message["To"] = to_email
    message["Subject"] = subject

    await aiosmtplib.send(
        message,
        hostname=settings.email_host,
        port=settings.email_port,
        start_tls=True,
        username=settings.email_user,
        password=settings.email_pass,
    )

    print(f"OTP sent successfully to {to_email}")