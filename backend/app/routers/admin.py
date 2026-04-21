"""
Admin & Database Maintenance Endpoints

Provides endpoints for:
- Flushing incomplete/failed records
- Getting database health status
- Resetting processing locks
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.utils.db_cleanup import flush_incomplete_records, get_cleanup_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/db-status", response_model=Dict[str, int])
async def get_database_status(db: Session = Depends(get_db)) -> Dict[str, int]:
    """
    Get current database status: count of candidates by processing status.
    
    Returns:
        Dict with counts of completed, processing, failed, and pending candidates
    """
    try:
        summary = get_cleanup_summary(db)
        return summary
    except Exception as e:
        logger.error("[ADMIN-ERROR] Failed to get database status: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flush-incomplete", response_model=Dict[str, Any])
async def flush_incomplete(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Flush all incomplete records (status != 'completed').
    
    Deletes:
    - Candidates with status: failed, processing, pending
    - All related education, experience, publication, skill, patent, book records
    
    Returns:
        Dict with counts of deleted records by type
    """
    try:
        logger.warning("[ADMIN] Flush incomplete records endpoint called")
        deleted = flush_incomplete_records(db, statuses=["failed", "processing", "pending"])
        
        return {
            "status": "success",
            "deleted": deleted,
            "total": sum(deleted.values()),
            "message": f"Successfully flushed {sum(deleted.values())} incomplete records"
        }
    except Exception as e:
        logger.error("[ADMIN-ERROR] Failed to flush incomplete records: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flush-all", response_model=Dict[str, Any])
async def flush_all(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    ⚠️  WARNING: FLUSH ALL CANDIDATES (regardless of status)
    
    Use this only for complete database reset during testing.
    Production use requires confirmation.
    
    Returns:
        Dict with counts of deleted records
    """
    try:
        logger.error("[ADMIN-WARNING] FLUSH ALL endpoint called - DELETING ALL CANDIDATES")
        deleted = flush_incomplete_records(db, statuses=["all"])
        
        return {
            "status": "success",
            "deleted": deleted,
            "total": sum(deleted.values()),
            "warning": "ALL candidates and related records have been permanently deleted"
        }
    except Exception as e:
        logger.error("[ADMIN-ERROR] Failed to flush all records: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))
