"""
Simplified CV processing: Extract PDF -> Send to GPT-4o -> Save to database
No page-by-page splitting, no Ollama fallback, single unified extraction.

Features:
- Comprehensive stage-by-stage logging with timings
- Detailed error reporting with root cause analysis
- Resource usage tracking
- Idempotency checks to prevent duplicate processing
"""
from __future__ import annotations

import logging
import time
import json
import re
from datetime import date, datetime
from typing import Dict, Any

from celery import group

from app.db import SessionLocal
from app.models.models import (
    Candidate, EducationRecord, WorkExperience, JournalPublication, ConferencePublication, Skill,
    Patent, Book, SupervisionRecord, PublicationAuthor, TopicCluster, CollaborationEdge, ExtractionRun
)
from app.services.extractor import CVExtractorService
from app.schemas.extraction import AcademicProfileExtraction, CoreProfileExtraction, SkillsAndIPExtraction
from app.services.llm_router import llm_router
from app.services.pdf_parser import extract_pdf_text
from app.worker import celery_app

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ============================================================================
# Logging Configuration & Utils
# ============================================================================

STAGE_SEPARATOR = "=" * 110
SUBSECTION_SEPARATOR = "─" * 110


def log_stage_start(stage_num: int, stage_name: str, task_id: str, candidate_id: int):
    """Log the start of a processing stage."""
    logger.info(STAGE_SEPARATOR)
    logger.info(
        "[STAGE-%d] %s | TaskID: %s | CandidateID: %d",
        stage_num, stage_name.upper(), task_id, candidate_id
    )
    logger.info(STAGE_SEPARATOR)

def _parse_date(value: str | None) -> date | None:
    """Parse date from various formats."""
    if not value:
        return None

    candidates = ["%Y-%m-%d", "%Y/%m/%d", "%m/%Y", "%Y", "%b %Y", "%B %Y"]
    for pattern in candidates:
        try:
            parsed = datetime.strptime(value.strip(), pattern)
            if pattern in {"%Y", "%m/%Y", "%b %Y", "%B %Y"}:
                return date(parsed.year, parsed.month, 1)
            return parsed.date()
        except ValueError:
            continue
    return None


def _date_from_parts(year: int | None, month: int | None) -> date | None:
    """Construct a safe date from year/month parts extracted from schema."""
    if not year:
        return None
    try:
        normalized_month = month if month and 1 <= int(month) <= 12 else 1
        return date(int(year), int(normalized_month), 1)
    except Exception:
        return None


def _split_authors(authors_text: str | None) -> list[str]:
    if not authors_text:
        return []
    normalized = authors_text.replace(" and ", ",")
    parts = [part.strip() for part in re.split(r"[,;]", normalized) if part.strip()]
    return parts


def _looks_like_candidate(author_name: str, candidate_name: str) -> bool:
    return author_name.strip().lower() == candidate_name.strip().lower()


def _email_conflicts(db, candidate_id: int, email: str | None) -> bool:
    if not email:
        return False
    return (
        db.query(Candidate)
        .filter(Candidate.email == email, Candidate.id != candidate_id)
        .first()
        is not None
    )


def _has_publication_signals(raw_text: str) -> bool:
    lowered = (raw_text or "").lower()
    signals = ["journal", "published", "conference", "volume", "issue", "doi", "proceedings"]
    return any(signal in lowered for signal in signals)


def _email_matches_candidate_name(name: str | None, email: str | None) -> bool:
    if not name or not email or "@" not in email:
        return True
    local_part = email.split("@", 1)[0].lower()
    tokens = [token.lower() for token in re.findall(r"[A-Za-z]{3,}", name)]
    if not tokens:
        return True
    return any(token in local_part for token in tokens)


def _section_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": payload.get("section"),
        "model_name": payload.get("model_name"),
        "provider": payload.get("provider"),
        "llm_summary": payload.get("llm_summary", {}),
    }


def _merge_llm_snapshots(section_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    merged = {
        "total_attempts": 0,
        "total_successes": 0,
        "total_failures": 0,
        "by_key": {},
        "events": [],
    }

    for payload in section_payloads:
        snapshot = payload.get("llm_summary") or {}
        merged["total_attempts"] += int(snapshot.get("total_attempts", 0) or 0)
        merged["total_successes"] += int(snapshot.get("total_successes", 0) or 0)
        merged["total_failures"] += int(snapshot.get("total_failures", 0) or 0)

        for env_name, stats in (snapshot.get("by_key") or {}).items():
            bucket = merged["by_key"].setdefault(
                env_name,
                {
                    "provider": stats.get("provider"),
                    "attempts": 0,
                    "successes": 0,
                    "failures": 0,
                    "last_error": None,
                    "last_request_preview": None,
                    "last_response_preview": None,
                },
            )
            bucket["attempts"] += int(stats.get("attempts", 0) or 0)
            bucket["successes"] += int(stats.get("successes", 0) or 0)
            bucket["failures"] += int(stats.get("failures", 0) or 0)
            if stats.get("last_error"):
                bucket["last_error"] = stats["last_error"]
            if stats.get("last_request_preview"):
                bucket["last_request_preview"] = stats["last_request_preview"]
            if stats.get("last_response_preview"):
                bucket["last_response_preview"] = stats["last_response_preview"]

        merged["events"].extend(snapshot.get("events", []))

    return merged


def _format_merged_summary(summary: dict[str, Any], title: str) -> str:
    lines = [
        "=" * 110,
        f"[{title}]",
        f"Total Attempts: {summary.get('total_attempts', 0)}",
        f"Total Successes: {summary.get('total_successes', 0)}",
        f"Total Failures: {summary.get('total_failures', 0)}",
    ]
    for env_name, stats in (summary.get("by_key") or {}).items():
        lines.append(
            f"  - {env_name} | provider={stats.get('provider')} | attempts={stats.get('attempts', 0)} | "
            f"successes={stats.get('successes', 0)} | failures={stats.get('failures', 0)}"
        )
        if stats.get("last_error"):
            lines.append(f"      last_error={stats['last_error']}")
        if stats.get("last_request_preview"):
            lines.append(f"      last_request={stats['last_request_preview']}")
        if stats.get("last_response_preview"):
            lines.append(f"      last_response={stats['last_response_preview']}")
    lines.append("=" * 110)
    return "\n".join(lines)


def _extract_section_payload(cv_text: str, section: str) -> dict[str, Any]:
    service = CVExtractorService()
    model = service.extract_section(cv_text, section)
    payload = model.model_dump(mode="json")
    payload["section"] = section
    payload["model_name"] = getattr(service, "model", None)
    payload["provider"] = getattr(service, "provider", None)
    payload["llm_summary"] = llm_router.get_stats_snapshot()
    return payload


@celery_app.task(name="extract_core_profile_section")
def extract_core_profile_section(cv_text: str) -> dict[str, Any]:
    payload = _extract_section_payload(cv_text, "core")
    logger.info(
        "[SECTION-COMPLETE] core | name=%s | email=%s | edu=%d | exp=%d",
        payload.get("name"),
        payload.get("email"),
        len(payload.get("education", []) or []),
        len(payload.get("experience", []) or []),
    )
    return payload


@celery_app.task(name="extract_academic_profile_section")
def extract_academic_profile_section(cv_text: str) -> dict[str, Any]:
    payload = _extract_section_payload(cv_text, "academic")
    logger.info(
        "[SECTION-COMPLETE] academic | publications=%d | supervision=%d | books=%d",
        len(payload.get("publications", []) or []),
        len(payload.get("supervision", []) or []),
        len(payload.get("books", []) or []),
    )
    return payload


@celery_app.task(name="extract_skills_ip_section")
def extract_skills_ip_section(cv_text: str) -> dict[str, Any]:
    payload = _extract_section_payload(cv_text, "skills")
    logger.info(
        "[SECTION-COMPLETE] skills | patents=%d | skills=%d",
        len(payload.get("patents", []) or []),
        len(payload.get("skills", []) or []),
    )
    return payload


@celery_app.task(
    name="process_cv",
    bind=True,
    acks_late=True,           # Only acknowledge after successful completion
    max_retries=2,            # Retry up to 2 times on transient failures
    time_limit=3600,          # Hard limit: 1 hour (kills task forcibly)
    soft_time_limit=3300,     # Soft limit: 55 min (allows graceful cleanup)
    ignore_result=False,      # Store result in Redis for later retrieval
)
def process_cv(self, candidate_id: int) -> Dict[str, Any]:
    """
    Process a CV: Extract PDF text -> Send to LLM -> Save to database.
    
    IDEMPOTENT: Safe to retry. Duplicate calls with same candidate_id will skip if already processed.
    
    Args:
        candidate_id: ID of the candidate record in the database
        
    Returns:
        Dictionary with candidate_id, final status, timing info, and error details if any
    """
    # =========================================================================
    # TASK INITIALIZATION & TIMING
    # =========================================================================
    task_start_time = time.time()
    task_id = self.request.id
    result = {
        "candidate_id": candidate_id,
        "task_id": task_id,
        "status": None,
        "name": None,
        "timings": {},
        "counts": {},
        "error": None,
        "error_stage": None,
    }
    
    logger.info("")
    logger.info(STAGE_SEPARATOR)
    logger.info("[TASK-START] ===== CV PROCESSING TASK STARTED =====")
    logger.info("[TASK-START] TaskID: %s | CandidateID: %d | Retry: %d/%d",
                task_id, candidate_id, self.request.retries, self.max_retries)
    logger.info(STAGE_SEPARATOR)
    
    db = SessionLocal()
    candidate = None

    try:
        # =====================================================================
        # STAGE 1: LOAD CANDIDATE
        # =====================================================================
        log_stage_start(1, "Load Candidate from Database", task_id, candidate_id)
        stage_time = time.time()
        
        logger.info("[1.1] Querying database for candidate...")
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        
        if not candidate:
            error_msg = f"Candidate not found in database (ID: {candidate_id})"
            logger.error("[1-LOAD-ERROR] %s", error_msg)
            result["status"] = "not_found"
            result["error"] = error_msg
            result["error_stage"] = 1
            return result
        
        stage_duration = time.time() - stage_time
        result["timings"]["load_candidate"] = stage_duration
        
        logger.info("[1.2] Candidate loaded successfully")
        logger.info("      ├─ Name: %s", candidate.name)
        logger.info("      ├─ Email: %s", candidate.email or "NOT PROVIDED")
        logger.info("      ├─ File Path: %s", candidate.file_path)
        logger.info("      ├─ Status: %s", candidate.status)
        logger.info("      └─ Duration: %.2f sec", stage_duration)
        
        # =====================================================================
        # IDEMPOTENCY CHECKS
        # =====================================================================
        if candidate.status == "completed":
            logger.info("[IDEMPOTENT-SKIP] Candidate already successfully processed")
            logger.info("      └─ Skipping to avoid duplicate extraction")
            result["status"] = "already_completed"
            result["name"] = candidate.name
            return result
        
        if candidate.status == "processing":
            logger.warning("[PROCESSING-CONFLICT] Another task is processing this candidate")
            logger.warning("      └─ This task will not proceed (duplicate prevention)")
            result["status"] = "processing_in_progress"
            return result
        
        # Mark as processing
        candidate.status = "processing"
        db.commit()
        logger.info("[1.3] Candidate status set to 'processing' (lock acquired)")

        # =====================================================================
        # STAGE 2: EXTRACT PDF TEXT
        # =====================================================================
        log_stage_start(2, "Extract Text from PDF", task_id, candidate_id)
        stage_time = time.time()
        
        if not candidate.file_path:
            error_msg = "Candidate file_path is empty or None"
            logger.error("[2-ERROR] %s", error_msg)
            result["status"] = "failed"
            result["error"] = error_msg
            result["error_stage"] = 2
            raise ValueError(error_msg)
        
        logger.info("[2.1] Reading PDF file: %s", candidate.file_path)
        try:
            cv_text = extract_pdf_text(candidate.file_path)
        except Exception as pdf_error:
            error_msg = f"PDF extraction failed: {str(pdf_error)}"
            logger.error("[2-PDF-ERROR] %s", error_msg)
            result["status"] = "failed"
            result["error"] = error_msg
            result["error_stage"] = 2
            raise Exception(error_msg)
        
        if not cv_text or len(cv_text.strip()) < 100:
            error_msg = f"PDF extraction yielded insufficient text ({len(cv_text) if cv_text else 0} chars, minimum required: 100)"
            logger.error("[2-PDF-ERROR] %s", error_msg)
            result["status"] = "failed"
            result["error"] = error_msg
            result["error_stage"] = 2
            raise ValueError(error_msg)
        
        stage_duration = time.time() - stage_time
        result["timings"]["pdf_extraction"] = stage_duration
        
        candidate.raw_text = cv_text.replace("\x00", "")
        db.commit()
        logger.info("[2.2] PDF extraction successful")
        logger.info("      ├─ Text length: %d characters", len(cv_text))
        logger.info("      ├─ Paragraphs: ~%d", len(cv_text.split('\n')))
        logger.info("      └─ Duration: %.2f sec", stage_duration)

        # =====================================================================
        # STAGE 3: LLM EXTRACTION
        # =====================================================================
        log_stage_start(3, "Send to LLM for Structured Extraction", task_id, candidate_id)
        stage_time = time.time()
        llm_router.reset_stats()
        
        logger.info("[3.1] Launching parallel section extraction tasks...")
        try:
            logger.info("[3.2] Fan-out: core + academic + skills sections")
            fanout = group(
                extract_core_profile_section.s(cv_text),
                extract_academic_profile_section.s(cv_text),
                extract_skills_ip_section.s(cv_text),
            ).apply_async()
            section_payloads = fanout.get(disable_sync_subtasks=False, timeout=1800)
            core_payload, academic_payload, skills_payload = section_payloads
            core = CoreProfileExtraction.model_validate(core_payload)
            academic = AcademicProfileExtraction.model_validate(academic_payload)
            skills_and_ip = SkillsAndIPExtraction.model_validate(skills_payload)

            extractor_service = CVExtractorService()
            extracted = extractor_service.aggregate_sections(cv_text, core, academic, skills_and_ip)
            result["llm_summary"] = _merge_llm_snapshots(section_payloads)
        except Exception as llm_error:
            error_msg = f"LLM extraction failed: {str(llm_error)}"
            logger.error("[3-LLM-ERROR] %s", error_msg)
            logger.error("[3-ERROR-DETAILS] Error type: %s", type(llm_error).__name__)
            result["status"] = "failed"
            result["error"] = error_msg
            result["error_stage"] = 3
            raise Exception(error_msg)
        
        if not extracted:
            error_msg = "LLM extraction returned None"
            logger.error("[3-LLM-ERROR] %s", error_msg)
            result["status"] = "failed"
            result["error"] = error_msg
            result["error_stage"] = 3
            raise ValueError(error_msg)
        
        if not extracted.name or extracted.name == "Extraction Failed":
            error_msg = f"LLM extraction returned invalid name: '{extracted.name}'"
            logger.error("[3-LLM-ERROR] %s", error_msg)
            if extracted.summary_of_profile:
                logger.error("[3-LLM-ERROR-REASON] %s", extracted.summary_of_profile)
            result["status"] = "failed"
            result["error"] = error_msg
            result["error_stage"] = 3
            raise ValueError(error_msg)
        
        stage_duration = time.time() - stage_time
        result["timings"]["llm_extraction"] = stage_duration
        result["name"] = extracted.name
        if "llm_summary" not in result:
            result["llm_summary"] = _merge_llm_snapshots([])
        
        logger.info("[3.3] LLM extraction successful")
        logger.info("      ├─ Candidate Name: %s", extracted.name)
        logger.info("      ├─ Email: %s", extracted.email or "NOT PROVIDED")
        logger.info("      ├─ Education Records: %d", len(extracted.education_records))
        logger.info("      ├─ Work Experiences: %d", len(extracted.work_experiences))
        logger.info("      ├─ Journal Publications: %d", len(extracted.journal_publications))
        logger.info("      ├─ Conference Publications: %d", len(extracted.conference_publications))
        logger.info("      ├─ Supervision Records: %d", len(extracted.supervision_records))
        logger.info("      ├─ Skills: %d", len(extracted.skills))
        logger.info("      ├─ Patents: %d", len(extracted.patents))
        logger.info("      ├─ Books: %d", len(extracted.books))
        logger.info("      └─ Duration: %.2f sec", stage_duration)
        logger.info(
            "[3.4] Aggregated section summary | core=%d | academic=%d | skills=%d",
            len(core.education) + len(core.experience),
            len(academic.publications) + len(academic.supervision) + len(academic.books),
            len(skills_and_ip.patents) + len(skills_and_ip.skills),
        )
        logger.info(
            _format_merged_summary(
                result["llm_summary"],
                title=f"LLM REQUEST SUMMARY | CandidateID: {candidate_id} | TaskID: {task_id}",
            )
        )

        # =====================================================================
        # STAGE 3.5: VALIDATION AGGREGATOR (PRE-PERSISTENCE)
        # =====================================================================
        publication_count = len(extracted.journal_publications) + len(extracted.conference_publications)
        if publication_count == 0 and _has_publication_signals(cv_text):
            logger.warning(
                "[3.5-VALIDATION] Publication signals found in raw text but extracted publications are empty. "
                "Triggering academic section re-extraction."
            )
            try:
                retry_service = CVExtractorService()
                academic_retry = retry_service.extract_section(cv_text, "academic")
                if isinstance(academic_retry, AcademicProfileExtraction):
                    academic = academic_retry
                    extracted = retry_service.aggregate_sections(cv_text, core, academic, skills_and_ip)
                    logger.info(
                        "[3.5-VALIDATION] Academic re-extraction complete | journals=%d | conferences=%d",
                        len(extracted.journal_publications),
                        len(extracted.conference_publications),
                    )
            except Exception as retry_error:
                logger.warning(
                    "[3.5-VALIDATION] Academic re-extraction failed: %s",
                    str(retry_error),
                    exc_info=True,
                )

        if extracted.email and not _email_matches_candidate_name(extracted.name, extracted.email):
            logger.warning(
                "[3.5-VALIDATION] Suspicious email/name mismatch detected. Clearing extracted email for manual review. "
                "name=%s | email=%s",
                extracted.name,
                extracted.email,
            )
            extracted.email = None

        try:
            if _email_conflicts(db, candidate.id, extracted.email):
                logger.warning(
                    "[4.1] Skipping duplicate email write for candidate_id=%d | email=%s",
                    candidate.id,
                    extracted.email,
                )
            db.add(ExtractionRun(
                candidate_id=candidate.id,
                provider=extracted.llm_provider or "litellm-router",
                model_name=extracted.llm_model_name or "talash-primary",
                prompt_version="v1-lossless",
                run_type="primary",
                status="completed",
                raw_response_json=getattr(extracted, "raw_llm_response", None) or candidate.raw_extraction_json,
                parsed_ok=True,
                error_message=None,
            ))
        except Exception:
            logger.warning("[3-RUN] Could not record extraction run metadata", exc_info=True)

        # =====================================================================
        # STAGE 4: PERSIST TO DATABASE
        # =====================================================================
        log_stage_start(4, "Persist Extracted Data to Database", task_id, candidate_id)
        stage_time = time.time()
        
        logger.info("[4.1] Updating candidate PII...")
        candidate.name = extracted.name or candidate.name
        candidate.email = candidate.email if _email_conflicts(db, candidate.id, extracted.email) else (extracted.email or candidate.email)
        candidate.phone = extracted.phone or candidate.phone
        candidate.linkedin_url = extracted.linkedin_url or candidate.linkedin_url
        candidate.personal_website = extracted.personal_website or candidate.personal_website
        candidate.other_urls = extracted.other_urls or candidate.other_urls
        candidate.summary = extracted.summary_of_profile or None
        try:
            candidate.raw_extraction_json = extracted.model_dump_json()
        except Exception:
            candidate.raw_extraction_json = json.dumps(extracted.model_dump(mode="json"), default=str)
        
        db_save_counts = {}
        
        # Education records
        logger.info("[4.2] Inserting education records...")
        db.query(EducationRecord).filter(EducationRecord.candidate_id == candidate.id).delete(synchronize_session=False)
        for edu in extracted.education_records:
            try:
                db.add(EducationRecord(
                    candidate_id=candidate.id,
                    institution_type=getattr(edu, "institution_type", None),
                    stage=edu.stage,
                    degree_title=edu.degree_title,
                    specialization=edu.specialization,
                    institution=edu.institution,
                    # The extraction schema no longer exposes board_or_university directly.
                    board_or_university=(
                        getattr(edu, "board_or_university", None)
                        or edu.institution
                    ),
                    start_year=edu.start_year,
                    start_month=getattr(edu, "start_month", None),
                    end_year=edu.end_year,
                    end_month=getattr(edu, "end_month", None),
                    marks_percentage=edu.marks_percentage,
                    cgpa=edu.cgpa,
                    cgpa_scale=edu.cgpa_scale,
                    normalized_cgpa=None,
                    institution_the_ranking=None,
                    institution_qs_ranking=None,
                    institution_ranking_source=getattr(edu, "institution_ranking_source", None),
                    institution_ranking_year=getattr(edu, "institution_ranking_year", None),
                    institution_ranking_value=getattr(edu, "institution_ranking_value", None),
                    gap_before_start_months=edu.gap_before_start_months,
                    gap_justified_by_experience=edu.gap_justified_by_experience,
                    evidence_text=getattr(edu, "evidence_text", None),
                    confidence_score=getattr(edu, "confidence_score", None),
                ))
            except Exception as err:
                logger.error("[4-EDU-ERROR] Failed to insert education record: %s | Data: %s", 
                           str(err), edu.dict())
                raise
        db_save_counts["education"] = len(extracted.education_records)
        logger.info("[4.2] ✓ Education: %d records queued", len(extracted.education_records))

        # Work experiences
        logger.info("[4.3] Inserting work experience records...")
        db.query(WorkExperience).filter(WorkExperience.candidate_id == candidate.id).delete(synchronize_session=False)
        for exp in extracted.work_experiences:
            try:
                db.add(WorkExperience(
                    candidate_id=candidate.id,
                    job_title=exp.job_title,
                    organization=exp.organization,
                    location=exp.location,
                    employment_type=exp.employment_type,
                    start_month=getattr(exp, "start_month", None),
                    start_year=getattr(exp, "start_year", None),
                    start_date=_date_from_parts(
                        getattr(exp, "start_year", None),
                        getattr(exp, "start_month", None),
                    ),
                    end_month=getattr(exp, "end_month", None),
                    end_year=getattr(exp, "end_year", None),
                    end_date=None
                    if (exp.is_current or False)
                    else _date_from_parts(
                        getattr(exp, "end_year", None),
                        getattr(exp, "end_month", None),
                    ),
                    is_current=exp.is_current or False,
                    is_academic_role=exp.is_academic_role,
                    overlaps_with_education=exp.overlaps_with_education,
                    job_responsibilities=getattr(exp, "job_responsibilities", None),
                    evidence_text=getattr(exp, "evidence_text", None),
                    confidence_score=getattr(exp, "confidence_score", None),
                ))
            except Exception as err:
                logger.error("[4-EXP-ERROR] Failed to insert work experience: %s | Data: %s", 
                           str(err), exp.dict())
                raise
        db_save_counts["work_experiences"] = len(extracted.work_experiences)
        logger.info("[4.3] ✓ Work Experience: %d records queued", len(extracted.work_experiences))

        # Journal publications
        logger.info("[4.4] Inserting journal publication records...")
        db.query(JournalPublication).filter(JournalPublication.candidate_id == candidate.id).delete(synchronize_session=False)
        for pub in extracted.journal_publications:
            try:
                journal_row = JournalPublication(
                    candidate_id=candidate.id,
                    title=pub.title,
                    authors=pub.authors,
                    journal_name=pub.journal_name,
                    issn=pub.issn,
                    doi=getattr(pub, "doi", None),
                    year=pub.year,
                    volume=getattr(pub, "volume", None),
                    issue=getattr(pub, "issue", None),
                    pages=getattr(pub, "pages", None),
                    wos_indexed=pub.wos_indexed or False,
                    scopus_indexed=pub.scopus_indexed or False,
                    quartile=pub.quartile,
                    impact_factor=pub.impact_factor,
                    authorship_role=pub.authorship_role,
                    author_position=pub.author_position,
                    topic_category=pub.topic_category,
                    is_with_student=pub.is_with_student or False,
                    abstract_or_summary=getattr(pub, "abstract_or_summary", None),
                    keywords_json=json.dumps(getattr(pub, "keywords", []) or []),
                    author_affiliations_json=json.dumps(getattr(pub, "author_affiliations", []) or []),
                    source_verification_url=getattr(pub, "source_verification_url", None),
                    confidence_score=getattr(pub, "confidence_score", None),
                )
                db.add(journal_row)
                db.flush()

                author_names = _split_authors(pub.authors)
                for index, author_name in enumerate(author_names, start=1):
                    db.add(PublicationAuthor(
                        candidate_id=candidate.id,
                        publication_type="journal",
                        publication_id=journal_row.id,
                        author_order=index,
                        author_name=author_name,
                        is_candidate=_looks_like_candidate(author_name, candidate.name),
                        is_corresponding=bool(pub.authorship_role and "Corresponding" in str(pub.authorship_role)),
                        affiliation=None,
                        normalized_author_key=author_name.lower(),
                    ))

                if pub.topic_category:
                    db.add(TopicCluster(
                        candidate_id=candidate.id,
                        publication_type="journal",
                        publication_id=journal_row.id,
                        cluster_name=pub.topic_category,
                        cluster_score=1.0,
                        assigned_by="llm",
                        model_version=extracted.llm_model_name or "talash-primary",
                    ))

                for author_name in author_names:
                    if not _looks_like_candidate(author_name, candidate.name):
                        db.add(CollaborationEdge(
                            candidate_id=candidate.id,
                            coauthor_name=author_name,
                            coauthor_affiliation=None,
                            publication_id=journal_row.id,
                            publication_type="journal",
                            edge_weight=1.0,
                            is_recurring=False,
                        ))
            except Exception as err:
                logger.error("[4-JOUR-ERROR] Failed to insert journal publication: %s | Title: %s", 
                           str(err), pub.title)
                raise
        db_save_counts["journal_publications"] = len(extracted.journal_publications)
        logger.info("[4.4] ✓ Journal Publications: %d records queued", len(extracted.journal_publications))

        # Conference publications
        logger.info("[4.5] Inserting conference publication records...")
        db.query(ConferencePublication).filter(ConferencePublication.candidate_id == candidate.id).delete(synchronize_session=False)
        for pub in extracted.conference_publications:
            try:
                conference_row = ConferencePublication(
                    candidate_id=candidate.id,
                    title=pub.title,
                    authors=pub.authors,
                    conference_name=pub.conference_name,
                    year=pub.year,
                    conference_series=pub.conference_series,
                    conference_location=getattr(pub, "conference_location", None),
                    publisher=getattr(pub, "publisher", None),
                    doi=getattr(pub, "doi", None),
                    is_a_star=pub.core_ranking == "A*" if pub.core_ranking else False,
                    core_ranking=pub.core_ranking,
                    indexed_in=pub.indexed_in,
                    authorship_role=pub.authorship_role,
                    author_position=pub.author_position,
                    topic_category=pub.topic_category,
                    is_with_student=pub.is_with_student or False,
                    abstract_or_summary=getattr(pub, "abstract_or_summary", None),
                    keywords_json=json.dumps(getattr(pub, "keywords", []) or []),
                    author_affiliations_json=json.dumps(getattr(pub, "author_affiliations", []) or []),
                    source_verification_url=getattr(pub, "source_verification_url", None),
                    confidence_score=getattr(pub, "confidence_score", None),
                )
                db.add(conference_row)
                db.flush()

                author_names = _split_authors(pub.authors)
                for index, author_name in enumerate(author_names, start=1):
                    db.add(PublicationAuthor(
                        candidate_id=candidate.id,
                        publication_type="conference",
                        publication_id=conference_row.id,
                        author_order=index,
                        author_name=author_name,
                        is_candidate=_looks_like_candidate(author_name, candidate.name),
                        is_corresponding=bool(pub.authorship_role and "Corresponding" in str(pub.authorship_role)),
                        affiliation=None,
                        normalized_author_key=author_name.lower(),
                    ))

                if pub.topic_category:
                    db.add(TopicCluster(
                        candidate_id=candidate.id,
                        publication_type="conference",
                        publication_id=conference_row.id,
                        cluster_name=pub.topic_category,
                        cluster_score=1.0,
                        assigned_by="llm",
                        model_version=extracted.llm_model_name or "talash-primary",
                    ))

                for author_name in author_names:
                    if not _looks_like_candidate(author_name, candidate.name):
                        db.add(CollaborationEdge(
                            candidate_id=candidate.id,
                            coauthor_name=author_name,
                            coauthor_affiliation=None,
                            publication_id=conference_row.id,
                            publication_type="conference",
                            edge_weight=1.0,
                            is_recurring=False,
                        ))
            except Exception as err:
                logger.error("[4-CONF-ERROR] Failed to insert conference publication: %s | Title: %s", 
                           str(err), pub.title)
                raise
        db_save_counts["conference_publications"] = len(extracted.conference_publications)
        logger.info("[4.5] ✓ Conference Publications: %d records queued", len(extracted.conference_publications))

        # Supervision records
        logger.info("[4.6] Inserting supervision records...")
        db.query(SupervisionRecord).filter(SupervisionRecord.candidate_id == candidate.id).delete(synchronize_session=False)
        for sup in extracted.supervision_records:
            try:
                db.add(SupervisionRecord(
                    candidate_id=candidate.id,
                    student_level=sup.student_level,
                    student_name=sup.student_name,
                    completion_year=sup.completion_year,
                    supervision_role=sup.supervision_role,
                    publications_with_student=sup.publications_with_student,
                    thesis_title=getattr(sup, "thesis_title", None),
                    evidence_text=getattr(sup, "evidence_text", None),
                    confidence_score=getattr(sup, "confidence_score", None),
                ))
            except Exception as err:
                logger.error("[4-SUP-ERROR] Failed to insert supervision record: %s | Student: %s", 
                           str(err), sup.student_name)
                raise
        db_save_counts["supervision_records"] = len(extracted.supervision_records)
        logger.info("[4.6] ✓ Supervision Records: %d records queued", len(extracted.supervision_records))

        # Skills
        logger.info("[4.7] Inserting skill records...")
        db.query(Skill).filter(Skill.candidate_id == candidate.id).delete(synchronize_session=False)
        for skill in extracted.skills:
            try:
                db.add(Skill(
                    candidate_id=candidate.id,
                    name=skill.name,
                    category=skill.category,
                    proficiency_level=getattr(skill, "proficiency_level", None),
                    years_of_experience=getattr(skill, "years_of_experience", None),
                    evidenced_in_work=skill.evidenced_in_work or False,
                    evidenced_in_research=skill.evidenced_in_research or False,
                    work_evidence=getattr(skill, "work_evidence", None),
                    research_evidence=getattr(skill, "research_evidence", None),
                    strength_of_evidence=skill.strength_of_evidence,
                    confidence_score=getattr(skill, "confidence_score", None),
                ))
            except Exception as err:
                logger.error("[4-SKILL-ERROR] Failed to insert skill: %s | Skill: %s", 
                           str(err), skill.name)
                raise
        db_save_counts["skills"] = len(extracted.skills)
        logger.info("[4.7] ✓ Skills: %d records queued", len(extracted.skills))

        # Patents
        logger.info("[4.8] Inserting patent records...")
        db.query(Patent).filter(Patent.candidate_id == candidate.id).delete(synchronize_session=False)
        for patent in extracted.patents:
            try:
                db.add(Patent(
                    candidate_id=candidate.id,
                    patent_no=patent.patent_no,
                    title=patent.title,
                    inventors=patent.inventors,
                    date_filed=patent.date_filed,
                    date_granted=getattr(patent, "date_granted", None),
                    country_of_filing=patent.country_of_filing,
                    online_link=patent.online_link,
                    inventor_role=patent.inventor_role,
                    status=patent.status,
                    evidence_text=getattr(patent, "evidence_text", None),
                    confidence_score=getattr(patent, "confidence_score", None),
                ))
            except Exception as err:
                logger.error("[4-PATENT-ERROR] Failed to insert patent: %s | Patent: %s", 
                           str(err), patent.title)
                raise
        db_save_counts["patents"] = len(extracted.patents)
        logger.info("[4.8] ✓ Patents: %d records queued", len(extracted.patents))

        # Books
        logger.info("[4.9] Inserting book records...")
        db.query(Book).filter(Book.candidate_id == candidate.id).delete(synchronize_session=False)
        for book in extracted.books:
            try:
                db.add(Book(
                    candidate_id=candidate.id,
                    title=book.title,
                    authors=book.authors,
                    isbn=book.isbn,
                    publisher=book.publisher,
                    year=book.year,
                    online_link=book.online_link,
                    authorship_role=book.authorship_role,
                    evidence_text=getattr(book, "evidence_text", None),
                    confidence_score=getattr(book, "confidence_score", None),
                ))
            except Exception as err:
                logger.error("[4-BOOK-ERROR] Failed to insert book: %s | Title: %s", 
                           str(err), book.title)
                raise
        db_save_counts["books"] = len(extracted.books)
        logger.info("[4.9] ✓ Books: %d records queued", len(extracted.books))

        # Final commit
        logger.info("[4.10] Committing all changes to database...")
        candidate.status = "completed"
        candidate.analysis_json = json.dumps(db_save_counts, default=str)
        db.commit()
        
        stage_duration = time.time() - stage_time
        result["timings"]["database_persistence"] = stage_duration
        result["counts"] = db_save_counts
        
        logger.info("[4.10] ✓ Commit successful - all data persisted")
        logger.info("       Summary:")
        for record_type, count in db_save_counts.items():
            logger.info("         ├─ %s: %d", record_type.replace("_", " ").title(), count)
        logger.info("       Duration: %.2f sec", stage_duration)

        # =====================================================================
        # TASK COMPLETION
        # =====================================================================
        total_duration = time.time() - task_start_time
        result["status"] = "completed"
        result["timings"]["total"] = total_duration
        
        logger.info("")
        logger.info(STAGE_SEPARATOR)
        logger.info("[TASK-SUCCESS] ===== CV PROCESSING COMPLETED SUCCESSFULLY =====")
        logger.info("[TASK-SUCCESS] CandidateID: %d | Name: %s", candidate_id, extracted.name)
        logger.info("[TASK-SUCCESS] Total Duration: %.2f sec", total_duration)
        logger.info("[TASK-SUCCESS] Stage Breakdown:")
        logger.info("       ├─ Load: %.2f sec", result["timings"].get("load_candidate", 0))
        logger.info("       ├─ PDF Extraction: %.2f sec", result["timings"].get("pdf_extraction", 0))
        logger.info("       ├─ LLM Extraction: %.2f sec", result["timings"].get("llm_extraction", 0))
        logger.info("       └─ DB Persistence: %.2f sec", result["timings"].get("database_persistence", 0))
        logger.info(STAGE_SEPARATOR)
        logger.info("")
        
        return result

    except Exception as e:
        total_duration = time.time() - task_start_time
        result["timings"]["total"] = total_duration
        result["status"] = "failed"
        result["error"] = str(e)
        result["llm_summary"] = llm_router.get_stats_snapshot()
        
        logger.info("")
        logger.info(STAGE_SEPARATOR)
        logger.error("[TASK-FAILED] ===== CV PROCESSING FAILED =====")
        logger.error("[TASK-FAILED] CandidateID: %d | TaskID: %s", candidate_id, task_id)
        logger.error("[TASK-FAILED] Error Stage: %s", result.get("error_stage", "UNKNOWN"))
        logger.error("[TASK-FAILED] Error Type: %s", type(e).__name__)
        logger.error("[TASK-FAILED] Error Message: %s", str(e))
        logger.error("[TASK-FAILED] Total Duration: %.2f sec", total_duration)
        logger.error("[TASK-FAILED] Traceback:", exc_info=True)
        logger.error(
            _format_merged_summary(
                result.get("llm_summary", _merge_llm_snapshots([])),
                title=f"LLM REQUEST SUMMARY | CandidateID: {candidate_id} | TaskID: {task_id}",
            )
        )
        logger.error(STAGE_SEPARATOR)
        logger.info("")
        
        # Update database status
        db.rollback()
        if candidate:
            try:
                candidate.status = "failed"
                db.commit()
                logger.info("[CLEANUP] Candidate status set to 'failed' in database")
            except Exception as db_err:
                logger.error("[CLEANUP-ERROR] Could not update candidate status: %s", str(db_err))
                db.rollback()
        
        return result
    
    finally:
        db.close()
        logger.debug("[CLEANUP] Database connection closed")


