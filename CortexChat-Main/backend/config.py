"""
backend/config.py
Application configuration using Pydantic Settings
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # ─── App ─────────────────────────────
    app_name: str = "CortexChat"

    # CORS
    allowed_origins: str = "*"

    @property
    def allowed_origins_list(self):
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    # ─── Database ───────────────────────
    database_url: str = "sqlite+aiosqlite:///./cortexchat.db"
    # Uploads
    upload_dir: str = "uploads"

    # ─── JWT Security ───────────────────
    secret_key: str = "supersecretkey"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    @property
    def jwt_algorithm(self):
        return self.algorithm

    # ─── Email / OTP ────────────────────
    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_user: str = ""
    email_pass: str = ""

    # ─── AI Keys ────────────────────────
    groq_api_key: str = ""
    hf_api_key: str = ""

    # ─── Pydantic Config ────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


@lru_cache
def get_settings():
    return Settings()