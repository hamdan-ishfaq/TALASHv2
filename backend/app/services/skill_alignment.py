from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.models import CandidateAssessment, Skill

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillAlignmentResult:
    candidate_id: int
    skills_total: int
    skills_strong: int
    skills_partial: int
    score: float


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

    skills_strong = sum(1 for s in skills if (s.strength_of_evidence or "").lower().find("strong") >= 0)
    skills_partial = sum(1 for s in skills if (s.strength_of_evidence or "").lower().find("partial") >= 0)

    score = compute_skill_alignment_score(skills)

    assessment = (
        db.query(CandidateAssessment)
        .filter_by(candidate_id=candidate_id)
        .order_by(CandidateAssessment.generated_at.desc())
        .first()
    )
    if assessment:
        assessment.skill_alignment_score = score
        if not assessment.assessment_version:
            assessment.assessment_version = "skills_v1"
    else:
        db.add(
            CandidateAssessment(
                candidate_id=candidate_id,
                assessment_version="skills_v1",
                skill_alignment_score=score,
            )
        )

    db.commit()

    logger.info(
        "[Skills] candidate=%d | skills=%d | strong=%d | partial=%d | score=%.1f",
        candidate_id,
        len(skills),
        skills_strong,
        skills_partial,
        score,
    )

    return SkillAlignmentResult(
        candidate_id=candidate_id,
        skills_total=len(skills),
        skills_strong=skills_strong,
        skills_partial=skills_partial,
        score=score,
    )
