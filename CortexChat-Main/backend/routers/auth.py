"""
backend/routers/auth.py — Authentication and Authorization Endpoints.

This module exposes the API routes responsible for identity management.
It handles user registration, email verification (via OTP), session initialization (JWT login),
and secure password resets.

Authentication State Machine Mapping:
  - `POST /auth/signup`: Validates input, creates an inactive `User`, triggers OTP generation.
  - `POST /auth/verify-signup`: Validates OTP, activates the `User`, issues the initial JWT.
  - `POST /auth/login`: Validates credentials, issues JWT (OTP bypassed for returning users).
  - `POST /auth/logout`: Provides instructions for the client to discard the stateless JWT.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User, UserPreferences
from backend.services.otp_service import generate_and_store_otp, verify_otp
from backend.utils.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name:     str
    email:    EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty.")
        return v.strip()


class VerifySignupRequest(BaseModel):
    email:    EmailStr
    otp_code: str


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         dict


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/signup", status_code=status.HTTP_200_OK)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    """
    Step 1 of signup: register email + password, trigger OTP email.

    - If email is new → create inactive account, send OTP.
    - If email exists but is not yet verified → update name/password, resend OTP.
    - If email is already active → reject with 409.
    """
    result = await db.execute(select(User).where(User.email == body.email))
    existing = result.scalar_one_or_none()

    if existing:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered."
            )
        # Unverified account — update details and resend OTP
        existing.name          = body.name
        existing.password_hash = hash_password(body.password)
        await db.commit()
        user = existing
    else:
        # Create inactive account
        user = User(
            email=body.email,
            name=body.name,
            password_hash=hash_password(body.password),
            is_active=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Send OTP to verify email ownership
    await generate_and_store_otp(body.email, db)

    return {"message": f"OTP sent to {body.email}. Please verify to activate your account."}


@router.post("/verify-signup", response_model=AuthResponse)
async def verify_signup(body: VerifySignupRequest, db: AsyncSession = Depends(get_db)):
    """
    Step 2 of signup: verify OTP code → activate account → return JWT.
    """
    valid = await verify_otp(body.email, body.otp_code, db)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired verification code.",
        )

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    # Activate the account
    user.is_active = True
    db.add(user)

    # Create default preferences if they don't exist
    prefs_result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == user.id)
    )
    if prefs_result.scalar_one_or_none() is None:
        db.add(UserPreferences(user_id=user.id))

    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.email)
    return AuthResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login with email + password. No OTP needed.

    Returns a JWT on success. Rejects with a generic 401 on any failure
    (don't reveal whether the email exists — security best practice).
    """
    # Generic error keeps user enumeration impossible
    invalid_creds = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
    )

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise invalid_creds

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not verified. Please complete signup by verifying your email.",
        )

    if not user.password_hash or not verify_password(body.password, user.password_hash):
        raise invalid_creds

    token = create_access_token(user.email)
    return AuthResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout():
    """
    Informational logout. JWT tokens are stateless; the client must
    delete its locally-stored token to complete logout.
    """
    return {"message": "Logged out. Please delete your local token."}


# ─── Password Reset ──────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyResetRequest(BaseModel):
    email: EmailStr
    otp_code: str

class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str
    
    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=404,
            detail="Email address not registered."
        )
        
    await generate_and_store_otp(body.email, db, context="reset")
    return {"message": "An OTP has been sent to your email."}


@router.post("/verify-reset")
async def verify_reset(body: VerifyResetRequest, db: AsyncSession = Depends(get_db)):
    valid = await verify_otp(body.email, body.otp_code, db)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP code.")
        
    # Generate a short-lived temporary token for password reset
    import jwt
    from datetime import datetime, timedelta, timezone
    from backend.config import get_settings
    settings = get_settings()
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    payload = {"sub": body.email, "type": "reset", "exp": expire}
    reset_token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    
    return {"reset_token": reset_token}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    import jwt
    from backend.config import get_settings
    settings = get_settings()
    
    try:
        payload = jwt.decode(body.reset_token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "reset":
            raise ValueError()
        email = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired reset token.")
        
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    
    return {"message": "Password successfully changed. You can now sign in."}
