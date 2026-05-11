"""
supervision_analysis.py
-----------------------
Links supervision records to publications where the student name appears in author lists;
updates SupervisionRecord.publications_with_student (best-effort).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.models import Candidate, ConferencePublication, JournalPublication, SupervisionRecord

logger = logging.getLogger(__name__)


def _split_authors(authors_text: str | None) -> list[str]:
    if not authors_text:
        return []
    normalized = authors_text.replace(" and ", ",")
    return [p.strip() for p in re.split(r"[,;]", normalized) if p.strip()]


def _name_in_authors(student_name: str | None, authors_text: str | None) -> bool:
    if not student_name or not authors_text:
        return False
    st = student_name.strip().lower()
    if len(st) < 3:
        return False
    for a in _split_authors(authors_text):
        if st in a.lower() or a.lower() in st:
            return True
    return False


@dataclass
class SupervisionAnalysisResult:
    candidate_id: int
    records_updated: int

    def to_dict(self) -> dict:
        return {"candidate_id": self.candidate_id, "records_updated": self.records_updated}


def run_supervision_analysis(db: Session, candidate_id: int) -> SupervisionAnalysisResult:
    cand = db.query(Candidate).filter_by(id=candidate_id).first()
    if not cand:
        raise ValueError(f"Candidate {candidate_id} not found")

    journals = db.query(JournalPublication).filter_by(candidate_id=candidate_id).all()
    conferences = db.query(ConferencePublication).filter_by(candidate_id=candidate_id).all()
    records = db.query(SupervisionRecord).filter_by(candidate_id=candidate_id).all()

    updated = 0
    for rec in records:
        n = 0
        for j in journals:
            if _name_in_authors(rec.student_name, j.authors):
                n += 1
        for c in conferences:
            if _name_in_authors(rec.student_name, c.authors):
                n += 1
        if n != (rec.publications_with_student or 0):
            rec.publications_with_student = n
            updated += 1

    db.commit()
    logger.info("[SupervisionAnalysis] candidate=%d | records_updated=%d", candidate_id, updated)
    return SupervisionAnalysisResult(candidate_id=candidate_id, records_updated=updated)
