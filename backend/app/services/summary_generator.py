"""
summary_generator.py
--------------------
Phase C — Candidate Summary Generation.

Pulls all analysis data (education, experience, research, skills) and generates:
  1. A comprehensive executive summary (3-5 paragraphs) via LLM.
  2. An overall_rank score as weighted average of component scores.
  3. Stores results in Candidate.summary and CandidateAssessment.

LLM: Groq/Gemini rotation (llm_analysis.py) — NOT OpenRouter.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import (
    Candidate,
    CandidateAssessment,
    ConferencePublication,
    EducationGap,
    EducationRecord,
    EmploymentGap,
    JournalPublication,
    MissingInformationRequest,
    Skill,
    SupervisionRecord,
    WorkExperience,
)
from app.services.llm_analysis import analysis_llm_call, analysis_text_call

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Weights for overall rank
# ---------------------------------------------------------------------------
WEIGHT_EDUCATION = 0.25
WEIGHT_RESEARCH = 0.35
WEIGHT_EXPERIENCE = 0.25
WEIGHT_SKILLS = 0.15


# ---------------------------------------------------------------------------
# Research strength heuristic (used when no LLM score exists yet)
# ---------------------------------------------------------------------------
def _compute_research_score(
    journal_count: int,
    conference_count: int,
    supervision_count: int,
) -> float:
    """Simple heuristic: max 10 points from publications + supervision."""
    pub_score = min(journal_count * 0.8 + conference_count * 0.5, 7.0)
    sup_score = min(supervision_count * 0.5, 3.0)
    return round(min(pub_score + sup_score, 10.0), 1)


def _compute_skill_score(skills: list[Skill]) -> float:
    """Heuristic skill score based on evidence strength."""
    if not skills:
        return 0.0
    strongly = sum(1 for s in skills if s.strength_of_evidence and "Strongly" in s.strength_of_evidence)
    partially = sum(1 for s in skills if s.strength_of_evidence and "Partially" in s.strength_of_evidence)
    total = len(skills)
    if total == 0:
        return 0.0
    score = (strongly * 1.0 + partially * 0.5) / total * 10.0
    return round(min(score, 10.0), 1)


# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------
_SUMMARY_SYSTEM_PROMPT = """\
You are an expert HR recruiter writing executive candidate summaries for university faculty positions.
You will receive comprehensive structured data about a candidate including their education,
experience, publications, skills, and analysis scores.

Write a professional executive summary of 3-5 paragraphs covering:
1. Overall profile overview (name, highest qualification, key areas of expertise)
2. Educational background and institutional quality
3. Professional experience trajectory and career highlights
4. Research output and impact (publications, supervision, patents)
5. Key strengths, potential concerns, and overall recommendation

The summary should be insightful, data-driven, and suitable for a hiring committee.
Write in third person. Be specific with numbers and facts from the data.
Return ONLY the summary text, no JSON wrapping.
"""


def _build_summary_prompt(
    candidate: Candidate,
    education_records: list[EducationRecord],
    experiences: list[WorkExperience],
    journals: list[JournalPublication],
    conferences: list[ConferencePublication],
    supervisions: list[SupervisionRecord],
    skills: list[Skill],
    assessment: Optional[CandidateAssessment],
    edu_gaps: list[EducationGap],
    emp_gaps: list[EmploymentGap],
    missing_requests: list[MissingInformationRequest],
) -> str:
    data = {
        "candidate": {
            "name": candidate.name,
            "email": candidate.email,
            "phone": candidate.phone,
            "linkedin": candidate.linkedin_url,
        },
        "education": [
            {
                "stage": r.stage, "degree": r.degree_title,
                "institution": r.institution, "specialization": r.specialization,
                "start_year": r.start_year, "end_year": r.end_year,
                "cgpa": r.cgpa, "cgpa_scale": r.cgpa_scale,
                "normalized_cgpa": r.normalized_cgpa,
                "qs_ranking": r.institution_qs_ranking,
            }
            for r in education_records
        ],
        "experience": [
            {
                "title": e.job_title, "org": e.organization,
                "start": e.start_year, "end": e.end_year or ("present" if e.is_current else None),
                "academic": e.is_academic_role,
                "responsibilities": (e.job_responsibilities or "")[:200],
            }
            for e in experiences
        ],
        "journal_publications": len(journals),
        "conference_publications": len(conferences),
        "supervisions": len(supervisions),
        "skills_count": len(skills),
        "top_skills": [s.name for s in skills[:10]],
        "scores": {
            "education": assessment.education_strength_score if assessment else None,
            "experience": assessment.experience_strength_score if assessment else None,
            "research": assessment.research_strength_score if assessment else None,
        },
        "education_gaps": len(edu_gaps),
        "employment_gaps": len(emp_gaps),
        "missing_info_modules": [r.module_name for r in missing_requests],
    }
    return f"Candidate profile data:\n{json.dumps(data, indent=2, default=str)}"


# ---------------------------------------------------------------------------
# Main service function
# ---------------------------------------------------------------------------
def generate_candidate_summary(
    db: Session,
    candidate_id: int,
) -> dict:
    """
    Generate executive summary and compute overall rank.
    Returns dict with summary text and overall rank.
    """
    logger.info("[SummaryGen] Starting for candidate_id=%d", candidate_id)

    candidate = db.query(Candidate).filter_by(id=candidate_id).first()
    if not candidate:
        raise ValueError(f"Candidate {candidate_id} not found")

    # Load all related data
    education_records = db.query(EducationRecord).filter_by(candidate_id=candidate_id).all()
    experiences = db.query(WorkExperience).filter_by(candidate_id=candidate_id).all()
    journals = db.query(JournalPublication).filter_by(candidate_id=candidate_id).all()
    conferences = db.query(ConferencePublication).filter_by(candidate_id=candidate_id).all()
    supervisions = db.query(SupervisionRecord).filter_by(candidate_id=candidate_id).all()
    skills = db.query(Skill).filter_by(candidate_id=candidate_id).all()
    edu_gaps = db.query(EducationGap).filter_by(candidate_id=candidate_id).all()
    emp_gaps = db.query(EmploymentGap).filter_by(candidate_id=candidate_id).all()
    missing_requests = db.query(MissingInformationRequest).filter_by(candidate_id=candidate_id).all()

    # Get existing assessment
    assessment = (
        db.query(CandidateAssessment)
        .filter_by(candidate_id=candidate_id)
        .order_by(CandidateAssessment.generated_at.desc())
        .first()
    )

    # ------------------------------------------------------------------
    # 1. Compute component scores
    # ------------------------------------------------------------------
    edu_score = assessment.education_strength_score if assessment and assessment.education_strength_score else 5.0
    exp_score = assessment.experience_strength_score if assessment and assessment.experience_strength_score else 5.0
    research_score = assessment.research_strength_score if assessment and assessment.research_strength_score else \
        _compute_research_score(len(journals), len(conferences), len(supervisions))
    skill_score = assessment.skill_alignment_score if assessment and assessment.skill_alignment_score else \
        _compute_skill_score(skills)

    # Overall rank (weighted average)
    overall_rank = round(
        edu_score * WEIGHT_EDUCATION +
        research_score * WEIGHT_RESEARCH +
        exp_score * WEIGHT_EXPERIENCE +
        skill_score * WEIGHT_SKILLS,
        2,
    )

    # ------------------------------------------------------------------
    # 2. Generate executive summary via LLM
    # ------------------------------------------------------------------
    user_prompt = _build_summary_prompt(
        candidate, education_records, experiences,
        journals, conferences, supervisions, skills,
        assessment, edu_gaps, emp_gaps, missing_requests,
    )
    summary_text = analysis_text_call(_SUMMARY_SYSTEM_PROMPT, user_prompt, max_tokens=2048)
    llm_used = summary_text is not None

    if not summary_text:
        # Fallback: generate a basic summary from data
        parts = [f"{candidate.name} "]
        highest_edu = max(education_records, key=lambda r: r.end_year or 0, default=None)
        if highest_edu:
            parts.append(f"holds a {highest_edu.degree_title or highest_edu.stage} from {highest_edu.institution or 'an institution'}. ")
        parts.append(f"They have {len(experiences)} professional experience records ")
        parts.append(f"across various roles. ")
        parts.append(f"Their research portfolio includes {len(journals)} journal and {len(conferences)} conference publications. ")
        if supervisions:
            parts.append(f"They have supervised {len(supervisions)} students. ")
        parts.append(f"Overall assessment score: {overall_rank}/10.")
        summary_text = "".join(parts)

    # ------------------------------------------------------------------
    # 3. Update database
    # ------------------------------------------------------------------
    candidate.summary = summary_text

    if assessment:
        assessment.research_strength_score = research_score
        assessment.skill_alignment_score = skill_score
        assessment.overall_rank = overall_rank
        assessment.overall_summary = summary_text
        assessment.assessment_version = "m2_full"
    else:
        db.add(CandidateAssessment(
            candidate_id=candidate_id,
            assessment_version="m2_full",
            education_strength_score=edu_score,
            research_strength_score=research_score,
            experience_strength_score=exp_score,
            skill_alignment_score=skill_score,
            overall_rank=overall_rank,
            overall_summary=summary_text,
        ))

    try:
        db.commit()
        logger.info(
            "[SummaryGen] Done candidate=%d | overall_rank=%.2f | edu=%.1f | research=%.1f | exp=%.1f | skills=%.1f | llm=%s",
            candidate_id, overall_rank, edu_score, research_score, exp_score, skill_score, llm_used,
        )
    except Exception as exc:
        db.rollback()
        logger.error("[SummaryGen] DB commit failed for candidate %d: %s", candidate_id, exc)
        raise

    return {
        "candidate_id": candidate_id,
        "overall_rank": overall_rank,
        "education_score": edu_score,
        "research_score": research_score,
        "experience_score": exp_score,
        "skill_score": skill_score,
        "summary": summary_text,
        "llm_used": llm_used,
    }
