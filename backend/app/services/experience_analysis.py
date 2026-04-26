"""
experience_analysis.py
----------------------
Phase B — Professional Experience Analysis (Section 3.8 of spec).

What this does end-to-end:
  1. Reads WorkExperience rows for a candidate (already populated by Module 1).
  2. Reconstructs career timeline and computes total/academic/industry experience.
  3. Detects employment gaps between consecutive jobs.
  4. Cross-references gaps with EducationRecord to flag justified gaps.
  5. Analyses career progression (upward / lateral / mixed).
  6. Writes EmploymentGap rows.
  7. Calls Groq/Gemini to generate an experience strength score + narrative.
  8. Updates CandidateAssessment row with experience_strength_score.
  9. Detects missing fields and creates a MissingInformationRequest row.

Session pattern: sync SessionLocal() — matches existing cv_tasks.py pattern.
LLM: Groq/Gemini rotation (llm_analysis.py) — NOT OpenRouter.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import (
    Candidate,
    CandidateAssessment,
    EducationRecord,
    EmploymentGap,
    MissingInformationRequest,
    WorkExperience,
)
from app.services.llm_analysis import analysis_llm_call

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GAP_THRESHOLD_MONTHS = 3   # gaps shorter than this are ignored


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
def _exp_start_date(exp: WorkExperience) -> Optional[date]:
    if exp.start_year:
        m = exp.start_month or 1
        return date(exp.start_year, min(max(m, 1), 12), 1)
    return None


def _exp_end_date(exp: WorkExperience) -> Optional[date]:
    if exp.is_current:
        return date.today()
    if exp.end_year:
        m = exp.end_month or 12
        return date(exp.end_year, min(max(m, 1), 12), 1)
    return None


def _months_between(d1: date, d2: date) -> int:
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------
@dataclass
class _EmpGapInfo:
    gap_start: date
    gap_end: date
    gap_months: int
    prev_exp_id: int
    next_exp_id: int
    prev_title: str
    next_title: str


def _detect_employment_gaps(experiences: list[WorkExperience]) -> list[_EmpGapInfo]:
    """Find gaps between consecutive work experiences."""
    dated = []
    for exp in experiences:
        start = _exp_start_date(exp)
        end = _exp_end_date(exp)
        if start and end:
            dated.append((start, end, exp))

    # Sort by start date
    dated.sort(key=lambda x: x[0])

    gaps: list[_EmpGapInfo] = []
    for i in range(len(dated) - 1):
        _, curr_end, curr_exp = dated[i]
        next_start, _, next_exp = dated[i + 1]

        if next_start <= curr_end:
            continue  # overlap or adjacent

        months = _months_between(curr_end, next_start)
        if months >= GAP_THRESHOLD_MONTHS:
            gaps.append(_EmpGapInfo(
                gap_start=curr_end,
                gap_end=next_start,
                gap_months=months,
                prev_exp_id=curr_exp.id,
                next_exp_id=next_exp.id,
                prev_title=curr_exp.job_title or "Unknown",
                next_title=next_exp.job_title or "Unknown",
            ))
    return gaps


# ---------------------------------------------------------------------------
# Gap justification via education
# ---------------------------------------------------------------------------
def _justify_gap_with_education(
    gap: _EmpGapInfo,
    education_records: list[EducationRecord],
) -> tuple[bool, str, Optional[int]]:
    """Check whether any education record overlaps with the employment gap."""
    for edu in education_records:
        edu_start = None
        edu_end = None
        if edu.start_year:
            edu_start = date(edu.start_year, edu.start_month or 1, 1)
        if edu.end_year:
            edu_end = date(edu.end_year, edu.end_month or 12, 1)

        if not edu_start:
            continue

        overlap_start = max(gap.gap_start, edu_start)
        overlap_end = min(gap.gap_end, edu_end or date.today())
        if overlap_start < overlap_end:
            desc = f"Pursuing {edu.degree_title or edu.stage or 'degree'} at {edu.institution or 'institution'}"
            return True, f"Gap covered by education: {desc} ({edu.start_year}–{edu.end_year or 'present'})", edu.id
    return False, "", None


# ---------------------------------------------------------------------------
# Career progression analysis
# ---------------------------------------------------------------------------
_SENIORITY_KEYWORDS = {
    # Higher number = more senior
    "intern": 1, "trainee": 1,
    "assistant": 2, "junior": 2, "associate": 2,
    "lecturer": 3, "engineer": 3, "developer": 3, "analyst": 3, "researcher": 3,
    "senior": 4, "lead": 4, "principal": 4, "staff": 4,
    "assistant professor": 5, "manager": 5, "head": 5,
    "associate professor": 6, "director": 6, "vp": 6,
    "professor": 7, "dean": 7, "chief": 7, "cto": 7, "ceo": 7,
}


def _estimate_seniority(title: str | None) -> int:
    if not title:
        return 0
    t = title.lower().strip()
    best = 0
    for keyword, level in _SENIORITY_KEYWORDS.items():
        if keyword in t:
            best = max(best, level)
    return best


def _assess_progression(experiences: list[WorkExperience]) -> str:
    """Assess career progression from chronological job titles."""
    dated = []
    for exp in experiences:
        start = _exp_start_date(exp)
        if start:
            dated.append((start, exp))

    if len(dated) < 2:
        return "Insufficient Data"

    dated.sort(key=lambda x: x[0])
    levels = [_estimate_seniority(exp.job_title) for _, exp in dated]

    # Check trend
    increases = sum(1 for i in range(len(levels) - 1) if levels[i + 1] > levels[i])
    decreases = sum(1 for i in range(len(levels) - 1) if levels[i + 1] < levels[i])
    total = len(levels) - 1

    if total == 0:
        return "Insufficient Data"
    if increases / total >= 0.6:
        return "Upward"
    if decreases / total >= 0.5:
        return "Declining"
    return "Lateral"


# ---------------------------------------------------------------------------
# Missing field detection
# ---------------------------------------------------------------------------
def _detect_missing_fields(experiences: list[WorkExperience]) -> list[str]:
    missing: list[str] = []
    for exp in experiences:
        if not exp.job_title:
            missing.append(f"Job title missing for role at {exp.organization or 'Unknown organization'}")
        if not exp.organization:
            missing.append(f"Organization name missing for {exp.job_title or 'Unknown role'}")
        if not exp.start_year:
            missing.append(f"Start year missing for {exp.job_title or 'role'} at {exp.organization or 'organization'}")
        if not exp.end_year and not exp.is_current:
            missing.append(f"End year missing for {exp.job_title or 'role'} at {exp.organization or 'organization'}")
    return list(dict.fromkeys(missing))  # deduplicate


# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------
_EXPERIENCE_SYSTEM_PROMPT = """\
You are an expert HR evaluator assessing professional experience for university faculty recruitment.
You will receive structured work experience data and must return ONLY a JSON object.

Your JSON must have exactly these keys:
{
  "experience_strength_score": <float 0.0-10.0>,
  "career_progression": "<one of: Upward / Lateral / Declining / Mixed / Insufficient Data>",
  "role_diversity": "<one of: Diverse / Specialized / Limited / N/A>",
  "academic_industry_balance": "<1-2 sentences on the mix of academic vs industry roles>",
  "gap_assessment": "<1-2 sentences on employment gaps and whether justified>",
  "strength_summary": "<3-5 sentences overall experience strength narrative>",
  "flags": ["<list any serious concerns, empty array if none>"]
}

Scoring guide for experience_strength_score (0-10):
  9-10: 15+ years of relevant experience, strong progression, leadership roles
  7-8:  10-15 years, good progression, relevant academic or industry roles
  5-6:  5-10 years, some progression, mixed relevance
  3-4:  2-5 years, limited progression or mostly unrelated roles
  1-2:  <2 years, no clear progression, significant unexplained gaps

Be conservative. Only cite facts present in the data. Return ONLY the JSON object, no extra text.
"""

_EMAIL_SYSTEM_PROMPT = """\
You are an HR assistant drafting professional emails to academic job candidates.
Return ONLY a JSON object with keys "subject" and "body".
The email should be polite, professional, and specific about what is missing.
Address the candidate by name. Sign off as "TALASH Recruitment System".
"""


def _build_experience_prompt(
    experiences: list[WorkExperience],
    gaps: list[_EmpGapInfo],
    gap_justifications: dict[int, tuple[bool, str]],
) -> str:
    exp_list = []
    for exp in sorted(experiences, key=lambda x: _exp_start_date(x) or date(1900, 1, 1)):
        exp_list.append({
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
            "responsibilities": (exp.job_responsibilities or "")[:300],
        })

    gap_list = []
    for i, g in enumerate(gaps):
        justified, just_text = gap_justifications.get(i, (False, ""))
        gap_list.append({
            "gap_months": g.gap_months,
            "from_role": g.prev_title,
            "to_role": g.next_title,
            "justified": justified,
            "justification": just_text,
        })

    data = {
        "work_experiences": exp_list,
        "employment_gaps": gap_list,
    }
    return f"Candidate experience data:\n{json.dumps(data, indent=2, default=str)}"


def _generate_missing_info_email(
    candidate_name: str,
    candidate_email: Optional[str],
    missing_fields: list[str],
) -> tuple[str, str]:
    """Returns (subject, body) for the missing info email."""
    prompt = (
        f"Candidate name: {candidate_name}\n"
        f"Candidate email: {candidate_email or 'unknown'}\n"
        f"Missing information items:\n"
        + "\n".join(f"  - {f}" for f in missing_fields)
        + "\n\nDraft a professional email requesting this information about their work experience."
    )
    result = analysis_llm_call(_EMAIL_SYSTEM_PROMPT, prompt, max_tokens=800)
    if isinstance(result, dict):
        return result.get("subject", "Request for Additional Information"), result.get("body", "")
    # Fallback
    subject = "Request for Additional Professional Experience Information"
    body = (
        f"Dear {candidate_name},\n\n"
        "Thank you for applying. To complete the evaluation of your application, "
        "we require the following additional information regarding your professional experience:\n\n"
        + "\n".join(f"  • {f}" for f in missing_fields)
        + "\n\nPlease provide the above details at your earliest convenience.\n\n"
        "Best regards,\nTALASH Recruitment System"
    )
    return subject, body


# ---------------------------------------------------------------------------
# DB write helpers
# ---------------------------------------------------------------------------
def _upsert_employment_gap(
    db: Session,
    candidate_id: int,
    gap: _EmpGapInfo,
    justified: bool,
    justification_text: str,
    edu_id: Optional[int],
) -> None:
    existing = (
        db.query(EmploymentGap)
        .filter_by(
            candidate_id=candidate_id,
            gap_start=gap.gap_start,
            gap_end=gap.gap_end,
        )
        .first()
    )
    if existing:
        existing.gap_months = gap.gap_months
        existing.justified = justified
        existing.justification_text = justification_text
        existing.related_education_id = edu_id
    else:
        db.add(EmploymentGap(
            candidate_id=candidate_id,
            gap_type="inter-employment",
            gap_start=gap.gap_start,
            gap_end=gap.gap_end,
            gap_months=gap.gap_months,
            justified=justified,
            justification_text=justification_text,
            related_education_id=edu_id,
        ))


def _upsert_assessment_experience(
    db: Session,
    candidate_id: int,
    score: float,
    summary: str,
    llm_data: dict,
) -> None:
    existing = (
        db.query(CandidateAssessment)
        .filter_by(candidate_id=candidate_id)
        .order_by(CandidateAssessment.generated_at.desc())
        .first()
    )
    if existing:
        existing.experience_strength_score = score
        existing.assessment_version = "m2_phase_b"
    else:
        db.add(CandidateAssessment(
            candidate_id=candidate_id,
            assessment_version="m2_phase_b",
            experience_strength_score=score,
            overall_summary=summary,
            missing_sections_json=json.dumps(llm_data.get("flags", [])),
        ))


def _upsert_missing_info_request(
    db: Session,
    candidate_id: int,
    missing_fields: list[str],
    subject: str,
    body: str,
) -> None:
    existing = (
        db.query(MissingInformationRequest)
        .filter_by(candidate_id=candidate_id, module_name="experience_analysis")
        .first()
    )
    if existing:
        existing.missing_fields_json = json.dumps(missing_fields)
        existing.draft_email_subject = subject
        existing.draft_email_body = body
        existing.status = "draft"
    else:
        db.add(MissingInformationRequest(
            candidate_id=candidate_id,
            module_name="experience_analysis",
            missing_fields_json=json.dumps(missing_fields),
            draft_email_subject=subject,
            draft_email_body=body,
            status="draft",
        ))


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class ExperienceAnalysisResult:
    candidate_id: int
    records_processed: int
    total_experience_months: int
    academic_experience_months: int
    industry_experience_months: int
    gaps_detected: int
    gaps_justified: int
    experience_strength_score: Optional[float]
    career_progression: str
    role_diversity: str
    strength_summary: str
    missing_fields: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    llm_used: bool = False


# ---------------------------------------------------------------------------
# Main service function
# ---------------------------------------------------------------------------
def run_experience_analysis(
    db: Session,
    candidate_id: int,
) -> ExperienceAnalysisResult:
    """
    Entry point called by the router and by the full-pipeline task.
    Mutates DB rows and returns a structured result.
    """
    logger.info("[ExpAnalysis] Starting for candidate_id=%d", candidate_id)

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    experiences: list[WorkExperience] = (
        db.query(WorkExperience)
        .filter_by(candidate_id=candidate_id)
        .all()
    )
    education_records: list[EducationRecord] = (
        db.query(EducationRecord)
        .filter_by(candidate_id=candidate_id)
        .all()
    )

    if not experiences:
        logger.warning("[ExpAnalysis] No work experience records for candidate %d", candidate_id)
        return ExperienceAnalysisResult(
            candidate_id=candidate_id,
            records_processed=0,
            total_experience_months=0,
            academic_experience_months=0,
            industry_experience_months=0,
            gaps_detected=0,
            gaps_justified=0,
            experience_strength_score=None,
            career_progression="Insufficient Data",
            role_diversity="N/A",
            strength_summary="No work experience records found.",
            missing_fields=["All work experience records missing"],
        )

    # ------------------------------------------------------------------
    # 2. Compute experience durations
    # ------------------------------------------------------------------
    total_months = 0
    academic_months = 0
    industry_months = 0
    organizations_seen: set[str] = set()

    for exp in experiences:
        start = _exp_start_date(exp)
        end = _exp_end_date(exp)
        if start and end and end > start:
            dur = _months_between(start, end)
            total_months += dur
            if exp.is_academic_role:
                academic_months += dur
            else:
                industry_months += dur
        if exp.organization:
            organizations_seen.add(exp.organization.lower().strip())

    # ------------------------------------------------------------------
    # 3. Gap detection
    # ------------------------------------------------------------------
    gaps = _detect_employment_gaps(experiences)

    # ------------------------------------------------------------------
    # 4. Gap justification
    # ------------------------------------------------------------------
    gap_justifications: dict[int, tuple[bool, str]] = {}
    justified_count = 0

    for i, gap in enumerate(gaps):
        justified, just_text, edu_id = _justify_gap_with_education(gap, education_records)
        gap_justifications[i] = (justified, just_text)
        if justified:
            justified_count += 1
        _upsert_employment_gap(db, candidate_id, gap, justified, just_text, edu_id)

    # ------------------------------------------------------------------
    # 5. Career progression
    # ------------------------------------------------------------------
    progression = _assess_progression(experiences)

    # Role diversity
    if len(organizations_seen) >= 4:
        role_diversity = "Diverse"
    elif len(organizations_seen) >= 2:
        role_diversity = "Specialized"
    else:
        role_diversity = "Limited"

    # ------------------------------------------------------------------
    # 6. Missing field detection
    # ------------------------------------------------------------------
    missing_fields = _detect_missing_fields(experiences)

    # ------------------------------------------------------------------
    # 7. LLM assessment
    # ------------------------------------------------------------------
    user_prompt = _build_experience_prompt(experiences, gaps, gap_justifications)
    llm_result = analysis_llm_call(_EXPERIENCE_SYSTEM_PROMPT, user_prompt, max_tokens=1500)
    llm_used = llm_result is not None and isinstance(llm_result, dict)

    if llm_used and isinstance(llm_result, dict):
        exp_score = float(llm_result.get("experience_strength_score", 5.0))
        llm_progression = llm_result.get("career_progression", progression)
        llm_diversity = llm_result.get("role_diversity", role_diversity)
        strength_summary = llm_result.get("strength_summary", "")
        flags = llm_result.get("flags", [])
    else:
        # Heuristic fallback
        exp_score = min(max(total_months / 24.0, 1.0), 10.0)
        llm_progression = progression
        llm_diversity = role_diversity
        strength_summary = "LLM assessment unavailable. Heuristic score computed from experience duration."
        flags = ["LLM_UNAVAILABLE"]
        llm_result = {}

    # ------------------------------------------------------------------
    # 8. Write CandidateAssessment
    # ------------------------------------------------------------------
    _upsert_assessment_experience(db, candidate_id, exp_score, strength_summary, llm_result)

    # ------------------------------------------------------------------
    # 9. Missing information email
    # ------------------------------------------------------------------
    if missing_fields:
        cand = db.query(Candidate).filter_by(id=candidate_id).first()
        cand_name = cand.name if cand else "Candidate"
        cand_email = cand.email if cand else None
        subject, body = _generate_missing_info_email(cand_name, cand_email, missing_fields)
        _upsert_missing_info_request(db, candidate_id, missing_fields, subject, body)

    # ------------------------------------------------------------------
    # 10. Commit
    # ------------------------------------------------------------------
    try:
        db.commit()
        logger.info(
            "[ExpAnalysis] Done candidate=%d | score=%.1f | gaps=%d | justified=%d | "
            "total_months=%d | academic=%d | industry=%d | missing=%d",
            candidate_id, exp_score, len(gaps), justified_count,
            total_months, academic_months, industry_months, len(missing_fields),
        )
    except Exception as exc:
        db.rollback()
        logger.error("[ExpAnalysis] DB commit failed for candidate %d: %s", candidate_id, exc)
        raise

    return ExperienceAnalysisResult(
        candidate_id=candidate_id,
        records_processed=len(experiences),
        total_experience_months=total_months,
        academic_experience_months=academic_months,
        industry_experience_months=industry_months,
        gaps_detected=len(gaps),
        gaps_justified=justified_count,
        experience_strength_score=exp_score,
        career_progression=llm_progression,
        role_diversity=llm_diversity,
        strength_summary=strength_summary,
        missing_fields=missing_fields,
        flags=flags if isinstance(flags, list) else [],
        llm_used=llm_used,
    )
