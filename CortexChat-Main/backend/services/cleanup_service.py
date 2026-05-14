"""
backend/services/cleanup_service.py — Background Document Retention Manager.

This module provides an asynchronous daemon (`auto_delete_old_documents`) that runs continuously
in the background. It periodically scans the `UserPreferences` table for users who have opted into
the "Auto-Delete Documents" feature and permanently erases any files (both physical disk files
and FAISS indices) older than 24 hours.
"""

import os
import shutil
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.database import get_db, AsyncSessionLocal
from backend.models.user import User, UserPreferences
from backend.models.file import UploadedFile
from backend.config import get_settings

settings = get_settings()

async def auto_delete_old_documents():
    """
    Periodic task that checks for documents older than 24 hours 
    for users who have 'auto_delete_docs' enabled.
    """
    # Wait for DB to be fully ready on startup (especially for Supabase)
    await asyncio.sleep(10)
    
    while True:
        try:
            print("Running auto-delete cleanup task...")
            async with AsyncSessionLocal() as db:
                # 1. Find all users with auto_delete enabled
                result = await db.execute(
                    select(UserPreferences).where(UserPreferences.auto_delete_docs == True)
                )
                prefs_list = result.scalars().all()
                
                for prefs in prefs_list:
                    cutoff_time = datetime.now() - timedelta(hours=24)
                    
                    # 2. Find files for this user older than 24h
                    file_result = await db.execute(
                        select(UploadedFile).where(
                            UploadedFile.user_id == prefs.user_id,
                            UploadedFile.created_at < cutoff_time
                        )
                    )
                    files_to_delete = file_result.scalars().all()
                    
                    for f in files_to_delete:
                        print(f"Auto-deleting old file: {f.original_name} (ID: {f.id}) for User: {f.user_id}")
                        
                        # Delete physical file
                        file_path = os.path.join(settings.upload_dir, str(f.user_id), f.stored_name)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            
                        # Delete FAISS index if exists
                        if f.faiss_index_path and os.path.exists(f.faiss_index_path):
                            shutil.rmtree(os.path.dirname(f.faiss_index_path), ignore_errors=True)
                            
                        # Delete from DB
                        await db.delete(f)
                
                await db.commit()
                
        except Exception as e:
            print(f"Error in auto-delete task: {e}")
            
        # Run every hour
        await asyncio.sleep(3600)
