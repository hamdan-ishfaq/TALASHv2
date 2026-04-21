"""
Database Cleanup Utility

Provides functions to flush incomplete, failed, or corrupted CV extraction records.
Useful for starting fresh without manually deleting database rows.
"""

import logging
from typing import Dict

from sqlalchemy.orm import Session

from app.models.models import (
    Candidate,
    EducationRecord,
    WorkExperience,
    JournalPublication,
    ConferencePublication,
    Skill,
    Patent,
    Book,
    SupervisionRecord,
)

logger = logging.getLogger(__name__)


def flush_incomplete_records(db: Session, statuses: list[str] = None) -> Dict[str, int]:
    """
    Delete all candidate records with incomplete statuses (not 'completed').
    This removes half-processed data to ensure clean subsequent runs.
    
    Args:
        db: SQLAlchemy database session
        statuses: List of statuses to flush. Defaults to ['failed', 'processing', 'pending']
                  Use ['all'] to flush ALL candidates regardless of status.
    
    Returns:
        Dict with counts of deleted records by type
    """
    if statuses is None:
        statuses = ["failed", "processing", "pending"]
    
    logger.info("=" * 100)
    logger.info("[CLEANUP] Starting database cleanup | Flushing statuses: %s", statuses)
    logger.info("=" * 100)
    
    deleted_counts = {
        "candidates": 0,
        "education": 0,
        "experience": 0,
        "journals": 0,
        "conferences": 0,
        "skills": 0,
        "patents": 0,
        "books": 0,
        "supervision": 0,
    }
    
    try:
        # Handle "all" special case
        if statuses == ["all"]:
            logger.warning("[CLEANUP-WARNING] 'all' status specified - FLUSHING ALL CANDIDATES")
            candidates_to_delete = db.query(Candidate).all()
        else:
            candidates_to_delete = db.query(Candidate).filter(Candidate.status.in_(statuses)).all()
        
        logger.info("[CLEANUP] Found %d candidates to delete with statuses: %s", 
                   len(candidates_to_delete), statuses)
        
        # Collect candidate IDs
        candidate_ids = [c.id for c in candidates_to_delete]
        
        if not candidate_ids:
            logger.info("[CLEANUP] No incomplete records found. Database is clean.")
            return deleted_counts
        
        # Delete related records (cascade will handle some, but be explicit)
        logger.info("[CLEANUP] Deleting related records...")
        
        deleted_counts["education"] = db.query(EducationRecord).filter(
            EducationRecord.candidate_id.in_(candidate_ids)
        ).delete(synchronize_session=False)
        logger.debug("[CLEANUP] Education records deleted: %d", deleted_counts["education"])
        
        deleted_counts["experience"] = db.query(WorkExperience).filter(
            WorkExperience.candidate_id.in_(candidate_ids)
        ).delete(synchronize_session=False)
        logger.debug("[CLEANUP] Work experience records deleted: %d", deleted_counts["experience"])
        
        deleted_counts["journals"] = db.query(JournalPublication).filter(
            JournalPublication.candidate_id.in_(candidate_ids)
        ).delete(synchronize_session=False)
        logger.debug("[CLEANUP] Journal publications deleted: %d", deleted_counts["journals"])
        
        deleted_counts["conferences"] = db.query(ConferencePublication).filter(
            ConferencePublication.candidate_id.in_(candidate_ids)
        ).delete(synchronize_session=False)
        logger.debug("[CLEANUP] Conference publications deleted: %d", deleted_counts["conferences"])
        
        deleted_counts["skills"] = db.query(Skill).filter(
            Skill.candidate_id.in_(candidate_ids)
        ).delete(synchronize_session=False)
        logger.debug("[CLEANUP] Skills deleted: %d", deleted_counts["skills"])
        
        deleted_counts["patents"] = db.query(Patent).filter(
            Patent.candidate_id.in_(candidate_ids)
        ).delete(synchronize_session=False)
        logger.debug("[CLEANUP] Patents deleted: %d", deleted_counts["patents"])
        
        deleted_counts["books"] = db.query(Book).filter(
            Book.candidate_id.in_(candidate_ids)
        ).delete(synchronize_session=False)
        logger.debug("[CLEANUP] Books deleted: %d", deleted_counts["books"])
        
        deleted_counts["supervision"] = db.query(SupervisionRecord).filter(
            SupervisionRecord.candidate_id.in_(candidate_ids)
        ).delete(synchronize_session=False)
        logger.debug("[CLEANUP] Supervision records deleted: %d", deleted_counts["supervision"])
        
        # Finally delete candidates
        deleted_counts["candidates"] = db.query(Candidate).filter(
            Candidate.id.in_(candidate_ids)
        ).delete(synchronize_session=False)
        logger.info("[CLEANUP] Candidate records deleted: %d", deleted_counts["candidates"])
        
        # Commit all deletions
        db.commit()
        
        # Summary
        total_deleted = sum(deleted_counts.values())
        logger.info("=" * 100)
        logger.info("[CLEANUP-SUCCESS] Database cleanup completed")
        logger.info("[CLEANUP-SUMMARY] Total records deleted: %d", total_deleted)
        for record_type, count in deleted_counts.items():
            if count > 0:
                logger.info("  ├─ %s: %d", record_type.upper(), count)
        logger.info("=" * 100)
        
        return deleted_counts
        
    except Exception as e:
        logger.error("=" * 100)
        logger.error("[CLEANUP-ERROR] Exception during cleanup: %s", str(e), exc_info=True)
        logger.error("=" * 100)
        db.rollback()
        raise


def get_cleanup_summary(db: Session) -> Dict[str, int]:
    """
    Get a summary of incomplete records without deleting them.
    Useful for previewing what will be flushed.
    
    Args:
        db: SQLAlchemy database session
    
    Returns:
        Dict with counts by status
    """
    summary = {
        "completed": db.query(Candidate).filter(Candidate.status == "completed").count(),
        "processing": db.query(Candidate).filter(Candidate.status == "processing").count(),
        "failed": db.query(Candidate).filter(Candidate.status == "failed").count(),
        "pending": db.query(Candidate).filter(Candidate.status == "pending").count(),
    }
    
    logger.info("[CLEANUP-SUMMARY]")
    logger.info("  ├─ COMPLETED: %d", summary["completed"])
    logger.info("  ├─ PROCESSING (incomplete): %d", summary["processing"])
    logger.info("  ├─ FAILED: %d", summary["failed"])
    logger.info("  └─ PENDING (not started): %d", summary["pending"])
    
    return summary
