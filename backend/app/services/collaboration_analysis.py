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

# Substrings commonly appearing in affiliation lines (lowercase)
_COUNTRY_MARKERS: tuple[str, ...] = (
    "pakistan", "india", "china", "usa", "united states", "u.s.", "uk", "united kingdom",
    "germany", "france", "canada", "australia", "japan", "korea", "saudi", "uae",
    "turkey", "italy", "spain", "netherlands", "sweden", "norway", "brazil", "mexico",
    "egypt", "malaysia", "singapore", "thailand", "vietnam", "viet nam", "bangladesh",
    "iran", "iraq", "jordan", "qatar", "kuwait", "austria", "switzerland", "belgium",
    "poland", "czech", "russia", "ukraine", "south africa", "nigeria", "kenya",
)


def _countries_in_text(text: str | None) -> set[str]:
    if not text:
        return set()
    t = text.lower()
    return {m for m in _COUNTRY_MARKERS if m in t}


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
    affiliations_populated: int = 0
    inferred_region_diversity: int = 0
    international_collaboration_hint: str = ""

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "unique_coauthors": self.unique_coauthors,
            "recurring_collaborators": self.recurring_collaborators,
            "total_edges": self.total_edges,
            "avg_coauthors_per_paper": round(self.avg_coauthors_per_paper, 2),
            "top_collaborators": self.top_collaborators[:15],
            "affiliations_populated": self.affiliations_populated,
            "inferred_region_diversity": self.inferred_region_diversity,
            "international_collaboration_hint": self.international_collaboration_hint,
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

    affil_hits = 0
    all_regions: set[str] = set()
    for e in edges:
        regs = _countries_in_text(e.coauthor_affiliation)
        if regs:
            affil_hits += 1
        all_regions |= regs

    region_div = len(all_regions)
    if affil_hits == 0:
        hint = "Co-author affiliations not populated; regional collaboration cannot be inferred."
    elif region_div >= 3:
        hint = "Multiple geographic regions inferred from co-author affiliations (likely international breadth)."
    elif region_div == 2:
        hint = "Two distinct regions suggested from affiliations — moderate international or cross-border collaboration."
    elif region_div == 1:
        hint = "Affiliations suggest a single dominant region; collaboration may be mostly domestic or data is sparse."
    else:
        hint = "Affiliation text present but no known country markers detected."
    hint += " (Heuristic over affiliation substrings — verify manually.)"

    result = CollaborationAnalysisResult(
        candidate_id=candidate_id,
        unique_coauthors=len(key_counts),
        recurring_collaborators=len(recurring_keys),
        total_edges=len(edges),
        avg_coauthors_per_paper=avg_co,
        top_collaborators=top,
        affiliations_populated=affil_hits,
        inferred_region_diversity=region_div,
        international_collaboration_hint=hint,
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
