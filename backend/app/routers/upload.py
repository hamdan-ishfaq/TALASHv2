from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import Candidate
from app.utils.scores import research_strength_on_ten
from worker.cv_tasks import process_cv

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["upload"])
DATA_DIR = Path("data/cvs")


def _is_pdf_magic(data: bytes) -> bool:
    return bool(data) and len(data) >= 5 and data[:5] == b"%PDF-"


def _upload_accepts_as_pdf(content_type: str | None, filename: str | None, data: bytes) -> bool:
    """Require PDF magic bytes; allow common browser MIME quirks when magic matches."""
    if not _is_pdf_magic(data):
        return False
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in ("application/pdf", "application/x-pdf", ""):
        return True
    if ct in ("application/octet-stream", "binary/octet-stream"):
        return True
    return (filename or "").lower().endswith(".pdf")


def _analysis_health_payload(raw: str | None) -> dict:
    """Surface whether post-extraction pipeline completed without pipeline_error."""
    if not raw:
        return {"healthy": False, "pipeline_error": None, "detail": "no_analysis_json"}
    try:
        aj = json.loads(raw)
    except Exception:
        return {"healthy": False, "pipeline_error": "invalid_json", "detail": "parse_error"}
    if not isinstance(aj, dict):
        return {"healthy": False, "pipeline_error": None, "detail": "invalid_shape"}
    err = aj.get("pipeline_error")
    if err:
        return {"healthy": False, "pipeline_error": str(err)}
    if aj.get("pipeline"):
        return {"healthy": True, "pipeline_error": None}
    return {"healthy": False, "pipeline_error": None, "detail": "missing_pipeline"}


class JobDescriptionUpdate(BaseModel):
    """Target role / job description for §3.9 skill–JD alignment (optional)."""

    target_job_description: str | None = Field(None, description="Full job description text to match against extracted skills")


@router.patch("/candidates/{candidate_id}/job-description")
def update_candidate_job_description(
    candidate_id: int,
    payload: JobDescriptionUpdate,
    db: Session = Depends(get_db),
) -> dict:
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found")
    candidate.target_job_description = payload.target_job_description
    db.commit()
    db.refresh(candidate)
    logger.info("[PATCH-JD] candidate_id=%s | len=%s", candidate_id, len(payload.target_job_description or ""))
    return {
        "candidate_id": candidate_id,
        "ok": True,
        "target_job_description_length": len(candidate.target_job_description or ""),
    }


@router.post("/upload")
async def upload_cv(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    """Upload and queue a CV for processing."""
    logger.info("=" * 80)
    logger.info("[UPLOAD-START] New CV upload received | filename=%s", file.filename)
    
    file_bytes = await file.read()
    if not file_bytes:
        logger.warning("[UPLOAD-FAIL] Empty file uploaded")
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if not _upload_accepts_as_pdf(file.content_type, file.filename, file_bytes):
        logger.warning(
            "[UPLOAD-FAIL] Not a PDF (content_type=%s, magic_ok=%s)",
            file.content_type,
            _is_pdf_magic(file_bytes),
        )
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported (file must start with %PDF- and use a PDF content type or .pdf name)",
        )

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
            "task_skipped": True,
            "message": "Same file hash as an existing candidate; Celery task not re-queued. Poll GET /candidates/{id} for progress.",
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
    """Dev-only: queue a PDF that already exists under ``data/cvs`` (POST ``?file_path=`` absolute or relative to CWD)."""
    logger.info("=" * 80)
    logger.info("[UPLOAD-PATH-START] Direct file upload from filesystem | path=%s", file_path)

    path = Path(file_path).expanduser()
    try:
        resolved = path.resolve(strict=False)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid path: {exc}") from exc

    data_root = DATA_DIR.resolve()
    try:
        resolved.relative_to(data_root)
    except ValueError:
        logger.error("[UPLOAD-PATH-FAIL] Path escapes CV directory | path=%s | root=%s", resolved, data_root)
        raise HTTPException(
            status_code=400,
            detail=f"file_path must resolve under the CV folder: {data_root}",
        )

    if not resolved.is_file():
        logger.error("[UPLOAD-PATH-FAIL] File not found: %s", resolved)
        raise HTTPException(status_code=404, detail=f"File not found: {resolved}")

    if resolved.suffix.lower() != ".pdf":
        logger.warning("[UPLOAD-PATH-FAIL] Not a PDF file: %s", resolved)
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_bytes = resolved.read_bytes()
    if not _is_pdf_magic(file_bytes):
        raise HTTPException(status_code=400, detail="File does not look like a PDF (missing %PDF- header)")

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    logger.info("[UPLOAD-PATH] File hash: %s | size: %d bytes", file_hash[:16], len(file_bytes))

    existing = db.query(Candidate).filter(Candidate.file_hash == file_hash).first()
    if existing:
        logger.warning("[UPLOAD-PATH-DUPLICATE] File already processed | candidate_id=%s", existing.id)
        return {
            "candidate_id": existing.id,
            "status": existing.status,
            "duplicate": True,
            "task": "skipped",
            "task_skipped": True,
            "message": "Same file hash as an existing candidate; Celery task not re-queued.",
        }

    # Create candidate
    logger.info("[DB-CREATE] Creating candidate from filesystem path")
    candidate = Candidate(
        name=resolved.stem,
        status="queued",
        file_hash=file_hash,
        file_path=str(resolved),
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
        "target_job_description": candidate.target_job_description,
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
                "board_or_university": rec.board_or_university,
                "qs_ranking": rec.institution_qs_ranking,
                "the_ranking": rec.institution_the_ranking,
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
                "organization_name": exp.organization,
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
                "publication_year": pub.year,
                "quartile": pub.quartile,
                "impact_factor": pub.impact_factor,
                "wos_indexed": pub.wos_indexed,
                "scopus_indexed": pub.scopus_indexed,
                "doi": pub.doi,
                "issn": pub.issn,
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
                "publication_year": pub.year,
                "core_ranking": pub.core_ranking,
                "is_a_star": pub.is_a_star,
                "publisher": pub.publisher,
                "indexed_in": pub.indexed_in,
                "conference_series": pub.conference_series,
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
                "online_link": book.online_link,
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
                "online_link": patent.online_link,
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
                "evidenced_in_work": skill.evidenced_in_work,
                "evidenced_in_research": skill.evidenced_in_research,
            }
            for skill in candidate.skills
        ],
        "assessments": [
            {
                "id": a.id,
                "education_score": a.education_strength_score,
                "experience_score": a.experience_strength_score,
                "research_score": research_strength_on_ten(a.research_strength_score),
                "skill_score": a.skill_alignment_score,
                "jd_alignment_score": getattr(a, "jd_alignment_score", None),
                "overall_rank": a.overall_rank,
                "summary": a.overall_summary,
            }
            for a in candidate.assessments
        ],
        "education_gaps": [
            {
                "from_stage": g.from_stage,
                "to_stage": g.to_stage,
                "gap_months": g.gap_months,
                "justified": g.justified_by_work,
                "justification": g.justification_text,
            }
            for g in candidate.education_gaps
        ],
        "employment_gaps": [
            {
                "gap_type": g.gap_type,
                "gap_months": g.gap_months,
                "gap_start": str(g.gap_start) if g.gap_start else None,
                "gap_end": str(g.gap_end) if g.gap_end else None,
                "justified": g.justified,
                "justification": g.justification_text,
            }
            for g in candidate.employment_gaps
        ],
    }

    pipeline_metrics: dict = {}
    if candidate.analysis_json:
        try:
            aj = json.loads(candidate.analysis_json)
            if isinstance(aj, dict) and isinstance(aj.get("pipeline"), dict):
                pipeline_metrics = aj["pipeline"]
            elif isinstance(aj, dict) and aj.get("pipeline_error"):
                pipeline_metrics = {
                    "analysis_failed": True,
                    "pipeline_error": str(aj["pipeline_error"]),
                }
        except Exception:
            pipeline_metrics = {}
    response["pipeline_metrics"] = pipeline_metrics
    response["analysis_health"] = _analysis_health_payload(candidate.analysis_json)

    logger.info("[GET-CANDIDATE-COMPLETE] Response prepared with all data")
    logger.info("=" * 80)
    
    return response

