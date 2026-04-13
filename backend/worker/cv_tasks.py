from __future__ import annotations

import logging
from datetime import date, datetime

from app.db import SessionLocal
from app.models.models import (
    Candidate, EducationRecord, WorkExperience, Publication, Skill,
    Patent, Book, SupervisionRecord
)
from app.services.page_extractor import PageByPageExtractor
from app.services.pdf_parser import extract_pdf_text
from app.worker import celery_app

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _parse_date(value: str | None) -> date | None:
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


def _fallback_extraction(cv_text: str) -> ExtractedCandidate:
    """Fallback extraction when Ollama is unavailable."""
    logger.info("[FALLBACK-EXTRACT] Running basic fallback extraction")
    
    # Try to extract name from first few non-empty lines
    lines = [line.strip() for line in cv_text.split('\n') if line.strip()]
    name = "Unknown Applicant"
    email = None
    
    if lines:
        # First non-empty line is likely the name
        name = lines[0][:100]  # Cap at 100 chars
        logger.info("[FALLBACK-EXTRACT] Extracted name: %s", name)
        
        # Try to find an email in the first 500 chars
        import re
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', cv_text[:500])
        if email_match:
            email = email_match.group(0)
            logger.info("[FALLBACK-EXTRACT] Extracted email: %s", email)
    
    # Create minimal candidate with fallback data
    fallback_candidate = ExtractedCandidate(
        name=name,
        email=email,
        summary="Fallback extraction (Ollama unavailable) - Basic PII extraction completed"
    )
    logger.info("[FALLBACK-EXTRACT] Fallback candidate created with name=%s", name)
    return fallback_candidate


def _generate_ai_summary(cv_text: str, host: str = "http://host.docker.internal:11434") -> str:
    """Generate summary using Ollama with timeout and error handling."""
    logger.info("[SUMMARY-STAGE] Starting AI summary generation")
    try:
        logger.debug("[SUMMARY] Connecting to Ollama at %s", host)
        from ollama import Client
        client = Client(host=host, timeout=30.0)
        
        prompt = (
            "Summarize this CV in 4-6 concise lines for evaluator review. "
            "Cover profile, core strengths, experience focus, and notable output.\n\n"
            f"CV text:\n{cv_text[:2000]}"
        )
        logger.debug("[SUMMARY] Sending prompt to Ollama (llama3.1 model)")
        response = client.chat(
            model="llama3.1",
            messages=[
                {"role": "system", "content": "You are a precise hiring assistant."},
                {"role": "user", "content": prompt},
            ],
            options={"num_ctx": 2048, "temperature": 0.2, "num_gpu": 1},
        )
        summary = (response.get("message", {}) or {}).get("content", "").strip()
        logger.info("[SUMMARY-SUCCESS] Summary generated (%d chars)", len(summary))
        return summary
    except Exception as e:
        logger.warning("[SUMMARY-FAILED] Could not generate summary: %s | Using fallback", str(e))
        return "Unable to generate summary (Ollama unavailable)"


@celery_app.task(name="process_cv", bind=True)
def process_cv(self, candidate_id: int) -> dict[str, str | int]:
    """Process a CV end-to-end: parse PDF -> extract data -> persist to DB."""
    logger.info("=" * 90)
    logger.info("[TASK-START] *** CV Processing Started *** | candidate_id=%s | task_id=%s", candidate_id, self.request.id)
    logger.info("=" * 90)
    
    db = SessionLocal()
    candidate: Candidate | None = None

    try:
        logger.info("[STAGE-1] Database lookup for candidate_id=%s", candidate_id)
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        
        if candidate is None:
            logger.error("[STAGE-1-ERROR] Candidate NOT FOUND in database | candidate_id=%s", candidate_id)
            return {"candidate_id": candidate_id, "status": "not_found"}
        
        logger.info("[STAGE-1-OK] Candidate found | name=%s | file_path=%s", candidate.name, candidate.file_path)
        
        logger.info("[STAGE-2] PDF Parsing stage starting")
        candidate.status = "processing"
        db.commit()
        logger.debug("[STAGE-2] Updated candidate status to 'processing'")
        
        if not candidate.file_path:
            raise ValueError("Candidate has no file_path set in database")
        
        logger.info("[STAGE-2] Reading PDF file from: %s", candidate.file_path)
        cv_text = extract_pdf_text(candidate.file_path)
        logger.info("[STAGE-2-OK] PDF extraction successful | extracted %d characters", len(cv_text))
        logger.debug("[STAGE-2] First 200 chars: %s...", cv_text[:200])
        
        candidate.raw_text = cv_text
        db.commit()
        logger.info("[STAGE-2-OK] Raw text saved to database")

        logger.info("[STAGE-3] LLM Extraction stage starting")
        extracted = None
        ollama_available = False
        try:
            logger.debug("[STAGE-3] Initializing PageByPageExtractor with Ollama")
            page_extractor = PageByPageExtractor(
                pdf_path=candidate.file_path,
                model="llama3.1",
                ollama_host="http://host.docker.internal:11434"
            )
            logger.info("[STAGE-3] Page extractor initialized")
            
            logger.debug("[STAGE-3] Starting page-by-page extraction")
            extracted = page_extractor.extract_all_pages()
            ollama_available = True
            
            logger.info("[STAGE-3-OK] Page-by-page extraction successful | name=%s | edu_count=%d | exp_count=%d | pub_count=%d", 
                       extracted.name, len(extracted.education), len(extracted.experience), len(extracted.publications))
        except Exception as extract_err:
            logger.warning("[STAGE-3-WARN] LLM extraction failed: %s | type=%s", str(extract_err), type(extract_err).__name__)
            logger.info("[STAGE-3-FALLBACK] Switching to fallback extraction (Ollama unavailable or failed)")
            extracted = _fallback_extraction(cv_text)
            logger.info("[STAGE-3-FALLBACK-OK] Fallback extraction complete | name=%s", extracted.name)

        logger.info("[STAGE-4] Commit 1: Writing core data (PII + Education + Experience)")
        
        old_name = candidate.name
        old_email = candidate.email
        candidate.name = extracted.name or candidate.name
        candidate.email = extracted.email or candidate.email
        logger.info("[STAGE-4] PII updated | name=%s -> %s | email=%s -> %s", 
                   old_name, candidate.name, old_email, candidate.email)

        logger.debug("[STAGE-4] Deleting old education records")
        db.query(EducationRecord).filter(EducationRecord.candidate_id == candidate.id).delete(
            synchronize_session=False
        )
        logger.info("[STAGE-4] Inserting %d education records", len(extracted.education))
        for i, edu in enumerate(extracted.education, 1):
            logger.debug("[STAGE-4-EDU-%d] degree=%s | institution=%s | year=%s | cgpa=%s", 
                        i, edu.degree, edu.institution, edu.year, edu.cgpa)
            db.add(EducationRecord(
                candidate_id=candidate.id,
                degree_level=edu.degree,
                title=edu.title,
                institution=edu.institution,
                passing_year=edu.year,
                cgpa=edu.cgpa,
            ))

        logger.debug("[STAGE-4] Deleting old work experience records")
        db.query(WorkExperience).filter(WorkExperience.candidate_id == candidate.id).delete(
            synchronize_session=False
        )
        logger.info("[STAGE-4] Inserting %d work experience records", len(extracted.experience))
        for i, exp in enumerate(extracted.experience, 1):
            logger.debug("[STAGE-4-EXP-%d] title=%s | org=%s | location=%s | current=%s", 
                        i, exp.job_title, exp.organization, exp.location, exp.is_current)
            db.add(WorkExperience(
                candidate_id=candidate.id,
                job_title=exp.job_title,
                organization=exp.organization,
                location=exp.location,
                start_date=_parse_date(exp.start_date),
                end_date=_parse_date(exp.end_date),
                is_current=bool(exp.is_current),
            ))

        # Persist publications
        logger.debug("[STAGE-4] Deleting old publication records")
        db.query(Publication).filter(Publication.candidate_id == candidate.id).delete(
            synchronize_session=False
        )
        logger.info("[STAGE-4] Inserting %d publication records", len(extracted.publications))
        for i, pub in enumerate(extracted.publications, 1):
            logger.debug("[STAGE-4-PUB-%d] title=%s | venue=%s | year=%s | type=%s | authors=%s", 
                        i, pub.title, pub.venue, pub.year, pub.type, 
                        ", ".join(pub.authors) if pub.authors else "N/A")
            db.add(Publication(
                candidate_id=candidate.id,
                title=pub.title or "Untitled",
                authors=", ".join(pub.authors) if pub.authors else None,
                venue=pub.venue,
                year=pub.year,
                type=pub.type,
            ))

        # Persist skills (if extracted)
        logger.debug("[STAGE-4] Deleting old skill records")
        db.query(Skill).filter(Skill.candidate_id == candidate.id).delete(
            synchronize_session=False
        )
        # Note: Skills are extracted in the ExtractedCandidate object
        if hasattr(extracted, 'skills') and extracted.skills:
            logger.info("[STAGE-4] Inserting %d skill records", len(extracted.skills))
            for i, skill in enumerate(extracted.skills, 1):
                logger.debug("[STAGE-4-SKILL-%d] name=%s | proficiency=%s | years=%s", 
                            i, skill.name, skill.proficiency_level, skill.years_of_experience)
                db.add(Skill(
                    candidate_id=candidate.id,
                    name=skill.name,
                    proficiency_level=skill.proficiency_level,
                    years_of_experience=skill.years_of_experience,
                ))
        else:
            logger.info("[STAGE-4] No skills found to persist")

        # Persist patents (if extracted)
        logger.debug("[STAGE-4] Deleting old patent records")
        db.query(Patent).filter(Patent.candidate_id == candidate.id).delete(
            synchronize_session=False
        )
        if hasattr(extracted, 'patents') and extracted.patents:
            logger.info("[STAGE-4] Inserting %d patent records", len(extracted.patents))
            for i, patent in enumerate(extracted.patents, 1):
                logger.debug("[STAGE-4-PATENT-%d] title=%s | inventors=%s | patent_no=%s | year=%s | status=%s", 
                            i, patent.title, patent.inventors, patent.patent_no, patent.year, patent.status)
                db.add(Patent(
                    candidate_id=candidate.id,
                    title=patent.title or "Untitled Patent",
                    inventors=", ".join(patent.inventors) if patent.inventors else None,
                    patent_no=patent.patent_no,
                    year=patent.year,
                    status=patent.status,
                ))
        else:
            logger.info("[STAGE-4] No patents found to persist")

        # Persist books (if extracted)
        logger.debug("[STAGE-4] Deleting old book records")
        db.query(Book).filter(Book.candidate_id == candidate.id).delete(
            synchronize_session=False
        )
        if hasattr(extracted, 'books') and extracted.books:
            logger.info("[STAGE-4] Inserting %d book records", len(extracted.books))
            for i, book in enumerate(extracted.books, 1):
                logger.debug("[STAGE-4-BOOK-%d] title=%s | authors=%s | publisher=%s | year=%s | isbn=%s", 
                            i, book.title, book.authors, book.publisher, book.year, book.isbn)
                db.add(Book(
                    candidate_id=candidate.id,
                    title=book.title or "Untitled Book",
                    authors=", ".join(book.authors) if book.authors else None,
                    publisher=book.publisher,
                    year=book.year,
                    isbn=book.isbn,
                ))
        else:
            logger.info("[STAGE-4] No books found to persist")

        # Persist supervision records (if extracted)
        logger.debug("[STAGE-4] Deleting old supervision records")
        db.query(SupervisionRecord).filter(SupervisionRecord.candidate_id == candidate.id).delete(
            synchronize_session=False
        )
        if hasattr(extracted, 'supervision') and extracted.supervision:
            logger.info("[STAGE-4] Inserting %d supervision records", len(extracted.supervision))
            for i, supervision in enumerate(extracted.supervision, 1):
                logger.debug("[STAGE-4-SUPER-%d] level=%s | student_name=%s | year=%s", 
                            i, supervision.level, supervision.student_name, supervision.year)
                db.add(SupervisionRecord(
                    candidate_id=candidate.id,
                    level=supervision.level,
                    student_name=supervision.student_name,
                    year=supervision.year,
                ))
        else:
            logger.info("[STAGE-4] No supervision records found to persist")

        candidate.status = "core_saved"
        db.commit()
        logger.info("[STAGE-4-OK] Core data committed to database (including publications & skills)")

        logger.info("[STAGE-5] Commit 2: Generating AI summary")
        summary = _generate_ai_summary(cv_text)
        candidate.summary = summary
        
        # Set final status based on whether Ollama was available
        if ollama_available:
            candidate.status = "completed"
        else:
            candidate.status = "completed_with_fallback"
        
        db.commit()
        logger.info("[STAGE-5-OK] Summary committed to database")

        logger.info("=" * 90)
        logger.info("[TASK-SUCCESS] *** CV Processing Completed Successfully ***")
        logger.info("[TASK-RESULT] candidate_id=%s | final_status=%s | name=%s", 
                   candidate_id, candidate.status, candidate.name)
        logger.info("=" * 90)

        return {"candidate_id": candidate_id, "status": candidate.status}

    except Exception as exc:
        logger.error("=" * 90)
        logger.error("[TASK-EXCEPTION] Unhandled exception during processing", exc_info=True)
        logger.error("[TASK-ERROR] Error type: %s | Message: %s", type(exc).__name__, str(exc))
        
        db.rollback()
        logger.debug("[TASK-ERROR] Database rollback executed")
        
        if candidate is not None:
            try:
                logger.debug("[TASK-ERROR] Setting candidate status to 'failed'")
                candidate.status = "failed"
                db.commit()
                logger.info("[TASK-ERROR-SAVED] Failed status persisted to database")
            except Exception as db_err:
                logger.error("[TASK-ERROR-DB-FAIL] Could not save error status: %s", str(db_err))
                db.rollback()
        
        logger.error("=" * 90)
        return {"candidate_id": candidate_id, "status": "failed"}
    
    finally:
        logger.debug("[CLEANUP] Closing database connection")
        db.close()
        logger.debug("[CLEANUP] Database connection closed | Task execution finished")
