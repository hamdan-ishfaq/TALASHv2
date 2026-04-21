"""
CV Queue Service - Queue CVs for processing via Celery.
Used by folder monitor as callback for automatic CV detection.
"""
import hashlib
import logging
from pathlib import Path

from app.db import SessionLocal
from app.models.models import Candidate
from worker.cv_tasks import process_cv

logger = logging.getLogger(__name__)


def queue_cv_from_path(file_path: str) -> dict:
    """
    Queue a CV for processing from filesystem path.
    Used by folder monitor as callback for automatic CV detection.
    Opens its own database session.
    """
    logger.info("=" * 80)
    logger.info("[FOLDER-MONITOR] CV file detected | path=%s", file_path)
    
    try:
        path = Path(file_path)
        
        if not path.exists():
            logger.error("[FOLDER-MONITOR-FAIL] File not found: %s", file_path)
            return {"status": "error", "reason": "file_not_found"}
        
        if not path.suffix.lower() == ".pdf":
            logger.warning("[FOLDER-MONITOR-FAIL] Not a PDF: %s", file_path)
            return {"status": "error", "reason": "not_pdf"}

        file_bytes = path.read_bytes()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        logger.info("[FOLDER-MONITOR] File hash: %s | size: %d bytes", file_hash[:16], len(file_bytes))

        # Open own DB session
        db = SessionLocal()
        try:
            existing = db.query(Candidate).filter(Candidate.file_hash == file_hash).first()
            if existing:
                logger.warning("[FOLDER-MONITOR-DUPLICATE] Already processed | candidate_id=%s", existing.id)
                return {"status": "duplicate", "candidate_id": existing.id}

            # Create candidate
            logger.info("[FOLDER-MONITOR] Creating candidate database record")
            candidate = Candidate(
                name=path.stem,
                status="queued",
                file_hash=file_hash,
                file_path=str(path),
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            logger.info("[FOLDER-MONITOR-OK] Candidate created | candidate_id=%s | name=%s", candidate.id, candidate.name)

            # Queue task
            logger.info("[FOLDER-MONITOR-CELERY] Queueing process_cv task | candidate_id=%s", candidate.id)
            async_result = process_cv.delay(candidate.id)
            logger.info("[FOLDER-MONITOR-CELERY-OK] Task queued | task_id=%s", async_result.id)
            logger.info("=" * 80)

            return {
                "status": "queued",
                "candidate_id": candidate.id,
                "task_id": async_result.id,
            }
        finally:
            db.close()
    
    except Exception as e:
        logger.error("[FOLDER-MONITOR-ERROR] Failed to process file: %s", str(e), exc_info=True)
        return {"status": "error", "reason": str(e)}
