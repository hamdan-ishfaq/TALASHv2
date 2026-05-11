from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.models import Candidate, CandidateAssessment, JournalPublication, Skill

logger = logging.getLogger(__name__)

# Expand short / acronym tokens so JD ↔ skill overlap is less brittle.
_JD_TOKEN_ALIASES: dict[str, tuple[str, ...]] = {
    "ml": ("machine", "learning"),
    "dl": ("deep", "learning"),
    "nlp": ("natural", "language"),
    "cv": ("computer", "vision", "image"),
    "se": ("software", "engineering"),
    "db": ("database", "sql"),
    "k8s": ("kubernetes",),
    "aws": ("amazon", "cloud"),
    "gcp": ("google", "cloud"),
    "llm": ("language", "model", "transformer"),
}

_JD_STOP = frozenset(
    """
    the and for are but not you all can had her was one our out day get has him his how man new now old see two way who boy did its let put say she too use any may per via role team work job
    """.split()
)


@dataclass(frozen=True)
class SkillAlignmentResult:
    candidate_id: int
    skills_total: int
    skills_strong: int
    skills_partial: int
    score: float  # evidence strength 0..10
    jd_score: float | None = None  # skills vs target JD 0..10
    jd_skills_matched: int = 0
    jd_publication_hits: int = 0


def _jd_tokens(jd: str) -> set[str]:
    raw = {w for w in re.findall(r"[a-z][a-z0-9\+\-\#\.]{2,}", jd.lower()) if w not in _JD_STOP}
    base = {w for w in raw if len(w) >= 3}
    expanded = set(base)
    for t in base:
        for alias in _JD_TOKEN_ALIASES.get(t, ()):
            if len(alias) >= 3:
                expanded.add(alias)
    return expanded


def _skill_tokens(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9\+\#\.]{2,}", (name or "").lower()) if len(w) >= 2}


def compute_jd_skill_alignment(
    skills: list[Skill],
    jd_text: str,
    publication_corpus: str,
) -> tuple[float | None, int, int]:
    """
    Heuristic overlap between extracted skills and target job description (§3.9).
    Returns (score 0..10 or None if no JD, matched_skill_count, publication_keyword_hits).
    """
    jd = (jd_text or "").strip()
    if not jd:
        return None, 0, 0

    jtokens = _jd_tokens(jd)
    if not jtokens:
        return 0.0, 0, 0

    matched = 0
    for s in skills:
        st = _skill_tokens(s.name)
        if not st:
            continue
        if st & jtokens:
            matched += 1
            continue
        sn = (s.name or "").lower()
        if any(t in sn for t in jtokens if len(t) >= 4):
            matched += 1

    pub_hits = 0
    if publication_corpus:
        pc = publication_corpus.lower()
        for t in jtokens:
            if len(t) >= 5 and t in pc:
                pub_hits += 1

    n = len(skills)
    if n == 0:
        base = 0.0
    else:
        base = (matched / n) * 8.0
    bonus = min(1.5, pub_hits * 0.25)
    score = round(min(10.0, base + bonus), 1)
    return score, matched, pub_hits


def compute_skill_alignment_score(skills: list[Skill]) -> float:
    """Offline heuristic score based on evidence strength (0..10)."""
    if not skills:
        return 0.0

    skills_strong = 0
    skills_partial = 0
    for skill in skills:
        strength = (skill.strength_of_evidence or "").lower()
        if "strong" in strength:
            skills_strong += 1
        elif "partial" in strength:
            skills_partial += 1

    total = len(skills)
    if total == 0:
        return 0.0

    score = (skills_strong * 1.0 + skills_partial * 0.5) / total * 10.0
    return round(min(score, 10.0), 1)


def compute_and_persist_skill_alignment(db: Session, candidate_id: int) -> SkillAlignmentResult:
    skills = db.query(Skill).filter_by(candidate_id=candidate_id).all()
    cand = db.query(Candidate).filter_by(id=candidate_id).first()

    skills_strong = sum(1 for s in skills if (s.strength_of_evidence or "").lower().find("strong") >= 0)
    skills_partial = sum(1 for s in skills if (s.strength_of_evidence or "").lower().find("partial") >= 0)

    score = compute_skill_alignment_score(skills)

    pub_parts: list[str] = []
    for j in db.query(JournalPublication).filter_by(candidate_id=candidate_id).all():
        pub_parts.append(" ".join(filter(None, [j.title, j.journal_name, j.abstract_or_summary])))
    publication_corpus = " ".join(pub_parts)[:12000]

    jd_score: float | None = None
    jd_matched = 0
    jd_pub_hits = 0
    if cand and (cand.target_job_description or "").strip():
        jd_score, jd_matched, jd_pub_hits = compute_jd_skill_alignment(
            skills,
            cand.target_job_description,
            publication_corpus,
        )

    assessment = (
        db.query(CandidateAssessment)
        .filter_by(candidate_id=candidate_id)
        .order_by(CandidateAssessment.generated_at.desc())
        .first()
    )
    if assessment:
        assessment.skill_alignment_score = score
        if jd_score is not None:
            assessment.jd_alignment_score = jd_score
        if not assessment.assessment_version:
            assessment.assessment_version = "skills_v1"
    else:
        db.add(
            CandidateAssessment(
                candidate_id=candidate_id,
                assessment_version="skills_v1",
                skill_alignment_score=score,
                jd_alignment_score=jd_score,
            )
        )

    db.commit()

    logger.info(
        "[Skills] candidate=%d | skills=%d | strong=%d | partial=%d | evidence=%.1f | jd=%s",
        candidate_id,
        len(skills),
        skills_strong,
        skills_partial,
        score,
        f"{jd_score:.1f}" if jd_score is not None else "n/a",
    )

    return SkillAlignmentResult(
        candidate_id=candidate_id,
        skills_total=len(skills),
        skills_strong=skills_strong,
        skills_partial=skills_partial,
        score=score,
        jd_score=jd_score,
        jd_skills_matched=jd_matched,
        jd_publication_hits=jd_pub_hits,
    )
