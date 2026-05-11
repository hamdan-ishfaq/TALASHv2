"""
collaboration_analysis.py
-------------------------
§3.7 Co-author patterns: recurring collaborators, network size, avg authors per paper.
Updates CollaborationEdge.is_recurring based on aggregated counts.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.models import Candidate, CollaborationEdge, ConferencePublication, JournalPublication

logger = logging.getLogger(__name__)


def _split_authors(authors_text: str | None) -> list[str]:
    if not authors_text:
        return []
    normalized = authors_text.replace(" and ", ",")
    parts = [p.strip() for p in re.split(r"[,;]", normalized) if p.strip()]
    return parts


@dataclass
class CollaborationAnalysisResult:
    candidate_id: int
    unique_coauthors: int = 0
    recurring_collaborators: int = 0
    total_edges: int = 0
    avg_coauthors_per_paper: float = 0.0
    top_collaborators: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "unique_coauthors": self.unique_coauthors,
            "recurring_collaborators": self.recurring_collaborators,
            "total_edges": self.total_edges,
            "avg_coauthors_per_paper": round(self.avg_coauthors_per_paper, 2),
            "top_collaborators": self.top_collaborators[:15],
        }


def run_collaboration_analysis(db: Session, candidate_id: int) -> CollaborationAnalysisResult:
    cand = db.query(Candidate).filter_by(id=candidate_id).first()
    if not cand:
        raise ValueError(f"Candidate {candidate_id} not found")

    edges = db.query(CollaborationEdge).filter_by(candidate_id=candidate_id).all()
    key_counts: Counter[str] = Counter()
    for e in edges:
        key = (e.coauthor_name or "").strip().lower()
        if key:
            key_counts[key] += 1

    recurring_keys = {k for k, v in key_counts.items() if v >= 2}

    for e in edges:
        key = (e.coauthor_name or "").strip().lower()
        e.is_recurring = key in recurring_keys

    # Papers for avg coauthors
    coauthor_counts: list[int] = []
    for j in db.query(JournalPublication).filter_by(candidate_id=candidate_id).all():
        authors = _split_authors(j.authors)
        others = [a for a in authors if a.strip().lower() != (cand.name or "").strip().lower()]
        coauthor_counts.append(len(others))
    for c in db.query(ConferencePublication).filter_by(candidate_id=candidate_id).all():
        authors = _split_authors(c.authors)
        others = [a for a in authors if a.strip().lower() != (cand.name or "").strip().lower()]
        coauthor_counts.append(len(others))

    avg_co = sum(coauthor_counts) / len(coauthor_counts) if coauthor_counts else 0.0

    top = [
        {"name": name, "shared_papers": count}
        for name, count in key_counts.most_common(15)
    ]

    result = CollaborationAnalysisResult(
        candidate_id=candidate_id,
        unique_coauthors=len(key_counts),
        recurring_collaborators=len(recurring_keys),
        total_edges=len(edges),
        avg_coauthors_per_paper=avg_co,
        top_collaborators=top,
    )
    db.commit()
    logger.info(
        "[Collaboration] candidate=%d | unique=%d | recurring=%d | edges=%d",
        candidate_id,
        result.unique_coauthors,
        result.recurring_collaborators,
        result.total_edges,
    )
    return result
