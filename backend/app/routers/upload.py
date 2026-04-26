from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import Candidate
from worker.cv_tasks import process_cv

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["upload"])
DATA_DIR = Path("data/cvs")


@router.post("/upload")
async def upload_cv(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    """Upload and queue a CV for processing."""
    logger.info("=" * 80)
    logger.info("[UPLOAD-START] New CV upload received | filename=%s", file.filename)
    
    if file.content_type != "application/pdf":
        logger.warning("[UPLOAD-FAIL] Invalid content type: %s (expected application/pdf)", file.content_type)
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_bytes = await file.read()
    if not file_bytes:
        logger.warning("[UPLOAD-FAIL] Empty file uploaded")
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    logger.info("[UPLOAD] File hash computed: %s | size: %d bytes", file_hash[:16], len(file_bytes))

    existing = db.query(Candidate).filter(Candidate.file_hash == file_hash).first()
    if existing:
        logger.warning("[UPLOAD-DUPLICATE] File already uploaded | candidate_id=%s | status=%s", existing.id, existing.status)
        return {
            "candidate_id": existing.id,
            "status": existing.status,
            "duplicate": True,
            "task": "skipped",
        }

    # Save file locally
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "cv.pdf").name
    stored_name = f"{file_hash[:12]}_{safe_name}"
    stored_path = DATA_DIR / stored_name
    logger.info("[UPLOAD] Saving file to: %s", stored_path)
    stored_path.write_bytes(file_bytes)
    logger.info("[UPLOAD-OK] File saved successfully")

    # Create database record
    logger.info("[DB-CREATE] Creating candidate database record")
    candidate = Candidate(
        name=Path(safe_name).stem,
        status="queued",
        file_hash=file_hash,
        file_path=str(stored_path),
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    logger.info("[DB-CREATE-OK] Candidate created | candidate_id=%s | name=%s", candidate.id, candidate.name)

    # Queue task
    logger.info("[CELERY-QUEUE] Queueing process_cv task | candidate_id=%s", candidate.id)
    async_result = process_cv.delay(candidate.id)
    logger.info("[CELERY-QUEUE-OK] Task queued | task_id=%s", async_result.id)
    logger.info("=" * 80)

    return {
        "candidate_id": candidate.id,
        "status": candidate.status,
        "duplicate": False,
        "task_id": async_result.id,
    }


@router.post("/upload-from-path")
def upload_from_path(file_path: str, db: Session = Depends(get_db)) -> dict:
    """Direct upload from filesystem (for testing). Usage: POST /upload-from-path?file_path=/path/to/cv.pdf"""
    logger.info("=" * 80)
    logger.info("[UPLOAD-PATH-START] Direct file upload from filesystem | path=%s", file_path)
    
    path = Path(file_path)
    if not path.exists():
        logger.error("[UPLOAD-PATH-FAIL] File not found: %s", file_path)
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    if not path.suffix.lower() == ".pdf":
        logger.warning("[UPLOAD-PATH-FAIL] Not a PDF file: %s", file_path)
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_bytes = path.read_bytes()
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    logger.info("[UPLOAD-PATH] File hash: %s | size: %d bytes", file_hash[:16], len(file_bytes))

    existing = db.query(Candidate).filter(Candidate.file_hash == file_hash).first()
    if existing:
        logger.warning("[UPLOAD-PATH-DUPLICATE] File already processed | candidate_id=%s", existing.id)
        return {"candidate_id": existing.id, "status": existing.status, "duplicate": True}

    # Create candidate
    logger.info("[DB-CREATE] Creating candidate from filesystem path")
    candidate = Candidate(
        name=path.stem,
        status="queued",
        file_hash=file_hash,
        file_path=str(path),
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    logger.info("[DB-CREATE-OK] Candidate created | candidate_id=%s", candidate.id)

    # Queue task
    logger.info("[CELERY-QUEUE] Queueing process_cv task")
    async_result = process_cv.delay(candidate.id)
    logger.info("[CELERY-QUEUE-OK] Task queued | task_id=%s", async_result.id)
    logger.info("=" * 80)

    return {
        "candidate_id": candidate.id,
        "status": candidate.status,
        "duplicate": False,
        "task_id": async_result.id,
    }


@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: int, db: Session = Depends(get_db)) -> dict:
    """Retrieve candidate data with all extracted information."""
    logger.info("=" * 80)
    logger.info("[GET-CANDIDATE] Retrieving candidate data | candidate_id=%s", candidate_id)
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        logger.warning("[GET-CANDIDATE-FAIL] Candidate not found | candidate_id=%s", candidate_id)
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found")
    
    logger.info("[GET-CANDIDATE-OK] Candidate found | name=%s | status=%s", candidate.name, candidate.status)
    
    # Build response with all extracted data
    response = {
        "id": candidate.id,
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "linkedin_url": candidate.linkedin_url,
        "status": candidate.status,
        "file_hash": candidate.file_hash,
        "file_path": candidate.file_path,
        "summary": candidate.summary,
        "education_records": [
            {
                "id": rec.id,
                "stage": rec.stage,
                "degree_title": rec.degree_title,
                "specialization": rec.specialization,
                "institution": rec.institution,
                "start_year": rec.start_year,
                "end_year": rec.end_year,
                "cgpa": rec.cgpa,
                "cgpa_scale": rec.cgpa_scale,
                "normalized_cgpa": rec.normalized_cgpa,
                "marks_percentage": rec.marks_percentage,
                "qs_ranking": rec.institution_qs_ranking,
            }
            for rec in candidate.education_records
        ],
        "work_experiences": [
            {
                "id": exp.id,
                "job_title": exp.job_title,
                "organization": exp.organization,
                "location": exp.location,
                "employment_type": exp.employment_type,
                "start_year": exp.start_year,
                "start_month": exp.start_month,
                "end_year": exp.end_year,
                "end_month": exp.end_month,
                "is_current": exp.is_current,
                "is_academic_role": exp.is_academic_role,
            }
            for exp in candidate.work_experiences
        ],
        "journal_publications": [
            {
                "id": pub.id,
                "title": pub.title,
                "authors": pub.authors,
                "journal_name": pub.journal_name,
                "year": pub.year,
                "quartile": pub.quartile,
                "impact_factor": pub.impact_factor,
                "authorship_role": pub.authorship_role,
            }
            for pub in candidate.journal_publications
        ],
        "conference_publications": [
            {
                "id": pub.id,
                "title": pub.title,
                "authors": pub.authors,
                "conference_name": pub.conference_name,
                "year": pub.year,
                "core_ranking": pub.core_ranking,
                "authorship_role": pub.authorship_role,
            }
            for pub in candidate.conference_publications
        ],
        "supervision_records": [
            {
                "id": rec.id,
                "student_level": rec.student_level,
                "student_name": rec.student_name,
                "completion_year": rec.completion_year,
                "supervision_role": rec.supervision_role,
            }
            for rec in candidate.supervision_records
        ],
        "books": [
            {
                "id": book.id,
                "title": book.title,
                "authors": book.authors,
                "publisher": book.publisher,
                "year": book.year,
                "isbn": book.isbn,
            }
            for book in candidate.books
        ],
        "patents": [
            {
                "id": patent.id,
                "title": patent.title,
                "inventors": patent.inventors,
                "patent_no": patent.patent_no,
                "status": patent.status,
            }
            for patent in candidate.patents
        ],
        "skills": [
            {
                "id": skill.id,
                "name": skill.name,
                "category": skill.category,
                "proficiency_level": skill.proficiency_level,
                "strength_of_evidence": skill.strength_of_evidence,
            }
            for skill in candidate.skills
        ],
        "assessments": [
            {
                "id": a.id,
                "education_score": a.education_strength_score,
                "experience_score": a.experience_strength_score,
                "research_score": a.research_strength_score,
                "skill_score": a.skill_alignment_score,
                "overall_rank": a.overall_rank,
                "summary": a.overall_summary,
            }
            for a in candidate.assessments
        ],
    }
    
    logger.info("[GET-CANDIDATE-COMPLETE] Response prepared with all data")
    logger.info("=" * 80)
    
    return response

