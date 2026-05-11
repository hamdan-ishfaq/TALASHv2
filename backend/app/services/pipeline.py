"""
pipeline.py
-----------
Orchestrates all post-extraction TALASH analyses for one candidate (Milestone 3 scope).
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.services.collaboration_analysis import run_collaboration_analysis
from app.services.education_analysis import run_education_analysis
from app.services.experience_analysis import run_experience_analysis
from app.services.missing_information_service import generate_missing_information_requests
from app.services.research_analysis import run_research_analysis
from app.services.skill_alignment import compute_and_persist_skill_alignment
from app.services.summary_generator import generate_candidate_summary
from app.services.supervision_analysis import run_supervision_analysis
from app.services.topic_analysis import run_topic_analysis

from app.models.models import Book, Patent

logger = logging.getLogger(__name__)


def _isbn_ok(isbn: str | None) -> bool:
    if not isbn:
        return False
    digits = re.sub(r"[^0-9Xx]", "", isbn)
    if len(digits) == 10:
        s = 0
        for i, ch in enumerate(digits[:9]):
            s += (10 - i) * int(ch)
        check = digits[9].upper()
        m = 11 - (s % 11)
        if m == 11:
            m = 0
        if m == 10:
            return check == "X"
        return str(m) == check
    if len(digits) == 13:
        s = sum(int(digits[i]) * (1 if i % 2 == 0 else 3) for i in range(12))
        check = (10 - (s % 10)) % 10
        return check == int(digits[12])
    return False


def _patent_format_ok(patent_no: str | None) -> bool:
    if not patent_no or len(patent_no.strip()) < 4:
        return False
    return bool(re.search(r"\d", patent_no))


def _build_verification_links(db: Session, candidate_id: int) -> dict[str, Any]:
    """Suggested public URLs for manual verification (books / patents)."""
    books_out: list[dict[str, Any]] = []
    for b in db.query(Book).filter_by(candidate_id=candidate_id).all():
        digits = re.sub(r"[^0-9Xx]", "", b.isbn or "")
        ol = f"https://openlibrary.org/isbn/{digits}.json" if len(digits) in (10, 13) else None
        books_out.append(
            {
                "id": b.id,
                "title": (b.title or "")[:120],
                "open_library_json": ol,
                "google_books_search": f"https://www.google.com/search?tbm=bks&q=isbn+{quote(digits)}" if digits else None,
            }
        )
    patents_out: list[dict[str, Any]] = []
    for p in db.query(Patent).filter_by(candidate_id=candidate_id).all():
        q = (p.patent_no or p.title or "").strip()
        patents_out.append(
            {
                "id": p.id,
                "title": (p.title or "")[:120],
                "google_patents_search": f"https://patents.google.com/?q={quote(q)}" if q else None,
            }
        )
    return {"books": books_out[:25], "patents": patents_out[:25]}


def run_local_ip_format_checks(db: Session, candidate_id: int) -> dict[str, Any]:
    """Non-network sanity checks for books/patents (format only)."""
    books = db.query(Book).filter_by(candidate_id=candidate_id).all()
    patents = db.query(Patent).filter_by(candidate_id=candidate_id).all()
    book_items = [
        {"id": b.id, "title": (b.title or "")[:80], "isbn_valid": _isbn_ok(b.isbn)}
        for b in books
    ]
    patent_items = [
        {"id": p.id, "title": (p.title or "")[:80], "number_plausible": _patent_format_ok(p.patent_no)}
        for p in patents
    ]
    return {
        "books_checked": len(book_items),
        "books_with_valid_isbn": sum(1 for x in book_items if x["isbn_valid"]),
        "patents_checked": len(patent_items),
        "patents_with_plausible_number": sum(1 for x in patent_items if x["number_plausible"]),
        "book_details": book_items[:20],
        "patent_details": patent_items[:20],
    }


def run_full_talash_analysis(db: Session, candidate_id: int) -> dict[str, Any]:
    """
    Run education, experience, research, skills, topic & collaboration analytics,
    supervision linking, missing-info drafts, executive summary.
    Each sub-service manages its own commits where applicable.
    """
    logger.info("[Pipeline] START candidate_id=%d", candidate_id)

    run_education_analysis(db, candidate_id)
    run_experience_analysis(db, candidate_id)
    research_res = run_research_analysis(db, candidate_id)
    skill_res = compute_and_persist_skill_alignment(db, candidate_id)

    topic = run_topic_analysis(db, candidate_id)
    collab = run_collaboration_analysis(db, candidate_id)
    run_supervision_analysis(db, candidate_id)
    ip_local = run_local_ip_format_checks(db, candidate_id)
    verify_links = _build_verification_links(db, candidate_id)

    gen = generate_missing_information_requests(db, candidate_id, force=False)
    db.commit()

    summary_result = generate_candidate_summary(db, candidate_id)

    out: dict[str, Any] = {
        "research_audit": {
            "grade": research_res.grade,
            "final_score": research_res.final_score,
            "normalized_score": research_res.normalized_score,
            "enrichment_audit": research_res.enrichment_audit,
            "warnings_head": (research_res.warnings or [])[:20],
        },
        "topic_variability": topic.to_dict(),
        "collaboration": collab.to_dict(),
        "ip_format_checks": ip_local,
        "verification_links": verify_links,
        "skill_alignment": {
            "evidence_score": skill_res.score,
            "jd_score": skill_res.jd_score,
            "jd_skills_matched": skill_res.jd_skills_matched,
            "jd_publication_hits": skill_res.jd_publication_hits,
        },
        "missing_info_modules": gen.generated_modules,
        "summary": {
            "overall_rank": summary_result.get("overall_rank"),
            "education_score": summary_result.get("education_score"),
            "research_score": summary_result.get("research_score"),
            "experience_score": summary_result.get("experience_score"),
            "skill_score": summary_result.get("skill_score"),
            "executive_summary": summary_result.get("summary"),
            "llm_used": summary_result.get("llm_used"),
        },
    }
    logger.info("[Pipeline] DONE candidate_id=%d | overall_rank=%s", candidate_id, out["summary"].get("overall_rank"))
    return out
