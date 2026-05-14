"""
backend/core/dependencies.py — FastAPI dependency injection helpers.

This module provides reusable dependency functions for FastAPI routes.
The primary dependency here is `get_current_user`, which acts as the core
authentication guard for protected endpoints (like creating chats, uploading files).

It performs the following:
1. Extracts the JWT (JSON Web Token) from the HTTP `Authorization: Bearer <token>` header.
2. Decodes the token to retrieve the user's identity (email).
3. Queries the database to ensure the user still exists and is active.
4. Returns the User ORM object directly to the route handler.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from backend.database import get_db
from backend.models.user import User
from backend.utils.security import decode_access_token

# Configure the HTTPBearer security scheme.
# auto_error=True means FastAPI will automatically reject requests (with HTTP 403)
# that completely lack an Authorization header, before our code even runs.
bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency: Validates the incoming JWT and returns the authenticated user object.

    Args:
        credentials: The extracted Bearer token from the incoming HTTP request.
        db: The active asynchronous database session (injected by FastAPI).

    Returns:
        User: The SQLAlchemy ORM model representing the currently authenticated user.

    Raises:
        HTTPException (401 Unauthorized): 
            - If the token is cryptographically invalid or expired.
            - If the user associated with the token has been deleted.
            - If the user account has been marked inactive/suspended.
    """
    # Pre-define the generic 401 Unauthorized exception.
    # We use a generic error message to prevent leaking account existence 
    # to potential attackers (e.g., differentiating between "bad token" vs "deleted user").
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Cryptographically verify and decode the JWT
    try:
        # decode_access_token will throw jwt.InvalidTokenError if the signature 
        # is wrong or if the 'exp' (expiration) claim is in the past.
        email = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise credentials_exception

    # 2. Verify the user against the database
    # Even if the token is mathematically valid, we must ensure the user still exists 
    # in the system. (e.g., They could have deleted their account after the token was issued).
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # 3. Final validation checks
    # Reject the request if the user is missing or if the account was disabled.
    if user is None or not user.is_active:
        raise credentials_exception

    # 4. Return the fully populated User ORM object to the endpoint logic
    return user
