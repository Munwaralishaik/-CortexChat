"""
backend/models/__init__.py — Unified ORM Model Registry.

This file acts as the central export point for all SQLAlchemy models in the application.
Importing all models here serves two critical purposes:
1. It simplifies imports elsewhere in the application (e.g., `from backend.models import User, Chat`).
2. It ensures that Alembic (the database migration tool) registers all metadata properly.
   For Alembic's `--autogenerate` feature to detect tables, the `Base.metadata` object 
   must know about every model class, which requires them to be imported into memory before 
   Alembic scans the metadata.
"""

from backend.models.user import User, OTPRecord, UserPreferences
from backend.models.chat import Chat, Message
from backend.models.file import UploadedFile

# Explicitly define the public API of this module.
# This prevents `from backend.models import *` from polluting the namespace.
__all__ = [
    "User",
    "OTPRecord",
    "UserPreferences",
    "Chat",
    "Message",
    "UploadedFile",
]
