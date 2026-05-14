"""
backend/utils/security.py — Cryptography and Authentication Primitives.
"""

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from backend.config import get_settings

settings = get_settings()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm
    )


def decode_access_token(token: str) -> str:
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm]
    )

    email: str = payload.get("sub", "")

    if not email:
        raise jwt.InvalidTokenError("Token subject is empty.")

    return email