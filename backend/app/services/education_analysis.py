"""
education_analysis.py
---------------------
Phase A — Educational Profile Analysis (Section 3.1 of spec).

What this does end-to-end:
  1. Reads EducationRecord rows for a candidate (already populated by Module 1).
  2. Normalises CGPA/percentage to a 0–4.0 scale and writes back.
  3. Looks up each institution in the QS Rankings XLSX.
  4. Detects gaps between consecutive education stages.
  5. Cross-references gaps with WorkExperience to flag justified gaps.
  6. Writes EducationGap rows.
  7. Writes InstitutionRanking rows.
  8. Calls Groq to generate an overall education strength score + narrative.
  9. Updates / inserts a CandidateAssessment row with education_strength_score.
  10. Detects missing fields and creates a MissingInformationRequest row.
  11. Updates EducationRecord rows with the computed values.

Session pattern: sync SessionLocal() — matches existing cv_tasks.py pattern.
LLM: Groq direct (llm_groq.py) — NOT OpenRouter.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import (
    CandidateAssessment,
    EducationGap,
    EducationRecord,
    InstitutionRanking,
    MissingInformationRequest,
    WorkExperience,
)
from app.services.llm_analysis import analysis_llm_call
from app.services.qs_lookup import QSRankingLookup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STAGE_ORDER = {
    "sse":    1,
    "matric": 1,
    "ssc":    1,
    "o-level":1,
    "hssc":   2,
    "fsc":    2,
    "fa":     2,
    "a-level":2,
    "intermediate": 2,
    "ug":     3,
    "bs":     3,
    "be":     3,
    "bsc":    3,
    "b.sc":   3,
    "bachelor":3,
    "b.e.":   3,
    "pg":     4,
    "ms":     4,
    "msc":    4,
    "m.sc":   4,
    "mphil":  4,
    "m.phil": 4,
    "master": 4,
    "mba":    4,
    "phd":    5,
    "ph.d":   5,
    "doctorate": 5,
}

GAP_THRESHOLD_MONTHS = 4   # gaps shorter than this are ignored


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------
def _normalise_cgpa(
    cgpa: Optional[float],
    cgpa_scale: Optional[float],
    marks_percentage: Optional[float],
) -> Optional[float]:
    """
    Return normalised score on 0–4.0 scale.
    Priority: CGPA (with scale) > marks_percentage.
    """
    if cgpa is not None and cgpa_scale and cgpa_scale > 0:
        if cgpa_scale == 4.0:
            return round(min(cgpa, 4.0), 3)
        return round(min((cgpa / cgpa_scale) * 4.0, 4.0), 3)
    if marks_percentage is not None and marks_percentage > 0:
        return round(min((marks_percentage / 100.0) * 4.0, 4.0), 3)
    return None


def _stage_key(stage: Optional[str]) -> int:
    """Map stage string to sort order (higher = more advanced)."""
    if not stage:
        return 99
    return STAGE_ORDER.get(stage.lower().strip(), 3)  # default UG


def _record_to_end_date(rec: EducationRecord) -> Optional[date]:
    if rec.end_year:
        m = rec.end_month or 6
        return date(rec.end_year, m, 1)
    return None


def _record_to_start_date(rec: EducationRecord) -> Optional[date]:
    if rec.start_year:
        m = rec.start_month or 1
        return date(rec.start_year, m, 1)
    return None


def _months_between(d1: date, d2: date) -> int:
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------
@dataclass
class _GapInfo:
    from_stage: str
    to_stage: str
    gap_start: date
    gap_end: date
    gap_months: int
    edu_end_id: int
    edu_start_id: int


def _detect_education_gaps(records: list[EducationRecord]) -> list[_GapInfo]:
    """Sort records by end date and find gaps between consecutive stages."""
    dated = [r for r in records if r.end_year]
    dated.sort(key=lambda r: (_record_to_end_date(r) or date(1900, 1, 1)))

    gaps: list[_GapInfo] = []
    for i in range(len(dated) - 1):
        current = dated[i]
        nxt     = dated[i + 1]
        end_d   = _record_to_end_date(current)
        start_d = _record_to_start_date(nxt)
        if not end_d or not start_d:
            continue
        if start_d <= end_d:
            continue   # no gap (or overlap — handled in experience analysis)
        months = _months_between(end_d, start_d)
        if months >= GAP_THRESHOLD_MONTHS:
            gaps.append(_GapInfo(
                from_stage=current.stage or "unknown",
                to_stage=nxt.stage or "unknown",
                gap_start=end_d,
                gap_end=start_d,
                gap_months=months,
                edu_end_id=current.id,
                edu_start_id=nxt.id,
            ))
    return gaps


# ---------------------------------------------------------------------------
# Gap justification via work experience
# ---------------------------------------------------------------------------
def _justify_gap(
    gap: _GapInfo,
    experiences: list[WorkExperience],
) -> tuple[bool, str, Optional[int]]:
    """
    Check whether any work experience overlaps with the gap period.
    Returns (justified, justification_text, work_experience_id).
    """
    for exp in experiences:
        exp_start: Optional[date] = None
        exp_end:   Optional[date] = None

        if exp.start_year:
            exp_start = date(exp.start_year, exp.start_month or 1, 1)
        if exp.end_year:
            exp_end = date(exp.end_year, exp.end_month or 12, 1)
        elif exp.is_current:
            exp_end = date.today()

        if not exp_start:
            continue

        # Overlap check: exp covers any part of the gap
        overlap_start = max(gap.gap_start, exp_start)
        overlap_end   = min(gap.gap_end, exp_end or date.today())
        if overlap_start < overlap_end:
            role_desc = f"{exp.job_title or 'Role'} at {exp.organization or 'organisation'}"
            return (
                True,
                f"Gap covered by: {role_desc} ({exp.start_year}–{exp.end_year or 'present'})",
                exp.id,
            )
    return False, "", None


# ---------------------------------------------------------------------------
# Missing field detection
# ---------------------------------------------------------------------------
def _detect_missing_fields(records: list[EducationRecord]) -> list[str]:
    missing: list[str] = []
    has_sse   = any(_stage_key(r.stage) == 1 for r in records)
    has_hssc  = any(_stage_key(r.stage) == 2 for r in records)
    has_ug    = any(_stage_key(r.stage) == 3 for r in records)

    if not has_sse:
        missing.append("SSE/Matric academic record (percentage, board, year)")
    if not has_hssc:
        missing.append("HSSC/Intermediate academic record (percentage, board, year)")
    if not has_ug:
        missing.append("Undergraduate degree record (CGPA, institution, year)")

    for rec in records:
        if _stage_key(rec.stage) >= 3:
            if rec.cgpa is None and rec.marks_percentage is None:
                missing.append(
                    f"Academic score (CGPA or percentage) for {rec.degree_title or rec.stage}"
                )
            if not rec.start_year:
                missing.append(f"Start year for {rec.degree_title or rec.stage}")
            if not rec.end_year:
                missing.append(f"End/completion year for {rec.degree_title or rec.stage}")
    return list(dict.fromkeys(missing))   # deduplicate, preserve order


# ---------------------------------------------------------------------------
# LLM: education strength assessment
# ---------------------------------------------------------------------------
_EDUCATION_SYSTEM_PROMPT = """\
You are an expert academic evaluator for university faculty recruitment.
You will receive structured education data for a candidate and must return ONLY a JSON object.

Your JSON must have exactly these keys:
{
  "education_strength_score": <float 0.0-10.0>,
  "progression_assessment": "<one of: Strong / Moderate / Weak / Insufficient Data>",
  "specialization_consistency": "<one of: Consistent / Divergent / Mixed / N/A>",
  "performance_trend": "<one of: Improving / Stable / Declining / Insufficient Data>",
  "institutional_quality_notes": "<1-2 sentences on institution quality based on rankings>",
  "gap_assessment": "<1-2 sentences on educational gaps and whether justified>",
  "strength_summary": "<3-5 sentences overall educational strength narrative>",
  "flags": ["<list any serious concerns, empty array if none>"]
}

Scoring guide for education_strength_score (0-10):
  9-10: PhD from ranked institution, strong CGPA throughout, no unjustified gaps
  7-8:  Strong UG+PG record, good institutions, minor gaps justified
  5-6:  Average performance, mixed institutions, some unexplained gaps
  3-4:  Below average CGPA, weak institutions, significant unexplained gaps
  1-2:  Incomplete records, very low performance, major concerns

Be conservative. Only cite facts present in the data. Return ONLY the JSON object, no extra text.
"""


def _build_education_prompt(
    records: list[EducationRecord],
    gaps: list[_GapInfo],
    gap_justifications: dict[int, tuple[bool, str]],
    qs_results: dict[str, dict],
) -> str:
    edu_list = []
    for r in sorted(records, key=lambda x: _stage_key(x.stage)):
        edu_list.append({
            "stage":            r.stage,
            "degree":           r.degree_title,
            "specialization":   r.specialization,
            "institution":      r.institution,
            "start_year":       r.start_year,
            "end_year":         r.end_year,
            "cgpa":             r.cgpa,
            "cgpa_scale":       r.cgpa_scale,
            "marks_percentage": r.marks_percentage,
            "normalized_cgpa":  r.normalized_cgpa,
            "qs_rank_2026":     qs_results.get(r.institution or "", {}).get("rank_2026"),
        })

    gap_list = []
    for i, g in enumerate(gaps):
        justified, just_text = gap_justifications.get(i, (False, ""))
        gap_list.append({
            "from_stage":     g.from_stage,
            "to_stage":       g.to_stage,
            "gap_months":     g.gap_months,
            "justified":      justified,
            "justification":  just_text,
        })

    data = {
        "education_records": edu_list,
        "education_gaps":    gap_list,
    }
    return f"Candidate education data:\n{json.dumps(data, indent=2)}"


# ---------------------------------------------------------------------------
# Missing information email
# ---------------------------------------------------------------------------
_EMAIL_SYSTEM_PROMPT = """\
You are an HR assistant drafting professional emails to academic job candidates.
Return ONLY a JSON object with keys "subject" and "body".
The email should be polite, professional, and specific about what is missing.
Address the candidate by name. Sign off as "TALASH Recruitment System".
"""


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
        + "\n\nDraft a professional email requesting this information."
    )
    result = analysis_llm_call(_EMAIL_SYSTEM_PROMPT, prompt, max_tokens=800)
    if isinstance(result, dict):
        return result.get("subject", "Request for Additional Information"), result.get("body", "")
    subject = "Request for Additional Academic Information"
    body = (
        f"Dear {candidate_name},\n\n"
        "Thank you for applying. To complete the evaluation of your application, "
        "we require the following additional information:\n\n"
        + "\n".join(f"  • {f}" for f in missing_fields)
        + "\n\nPlease provide the above details at your earliest convenience.\n\n"
        "Best regards,\nTALASH Recruitment System"
    )
    return subject, body


# ---------------------------------------------------------------------------
# DB write helpers
# ---------------------------------------------------------------------------
def _upsert_institution_ranking(
    db: Session,
    candidate_id: int,
    institution_name: str,
    qs_result: dict,
) -> None:
    existing = (
        db.query(InstitutionRanking)
        .filter_by(candidate_id=candidate_id, institution_name=institution_name, source="QS")
        .first()
    )
    if existing:
        existing.rank_value   = qs_result.get("rank_2026")
        existing.rank_band    = qs_result.get("rank_2026")
        existing.country      = qs_result.get("country")
        existing.source_year  = 2026
    else:
        db.add(InstitutionRanking(
            candidate_id=candidate_id,
            institution_name=institution_name,
            source="QS",
            source_year=2026,
            rank_value=qs_result.get("rank_2026"),
            rank_band=qs_result.get("rank_2026"),
            country=qs_result.get("country"),
            url="https://www.topuniversities.com/world-university-rankings",
        ))


def _upsert_education_gap(
    db: Session,
    candidate_id: int,
    gap: _GapInfo,
    justified: bool,
    justification_text: str,
    work_exp_id: Optional[int],
) -> None:
    existing = (
        db.query(EducationGap)
        .filter_by(
            candidate_id=candidate_id,
            from_stage=gap.from_stage,
            to_stage=gap.to_stage,
        )
        .first()
    )
    if existing:
        existing.gap_months          = gap.gap_months
        existing.gap_start           = gap.gap_start
        existing.gap_end             = gap.gap_end
        existing.justified_by_work   = justified
        existing.justification_text  = justification_text
        existing.evidence_work_experience_id = work_exp_id
    else:
        db.add(EducationGap(
            candidate_id=candidate_id,
            from_stage=gap.from_stage,
            to_stage=gap.to_stage,
            gap_months=gap.gap_months,
            gap_start=gap.gap_start,
            gap_end=gap.gap_end,
            justified_by_work=justified,
            justification_text=justification_text,
            evidence_work_experience_id=work_exp_id,
        ))


def _upsert_assessment(
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
        existing.education_strength_score = score
        existing.assessment_version       = "m2_phase_a"
    else:
        db.add(CandidateAssessment(
            candidate_id=candidate_id,
            assessment_version="m2_phase_a",
            education_strength_score=score,
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
        .filter_by(candidate_id=candidate_id, module_name="education_analysis")
        .first()
    )
    if existing:
        existing.missing_fields_json   = json.dumps(missing_fields)
        existing.draft_email_subject   = subject
        existing.draft_email_body      = body
        existing.status                = "draft"
    else:
        db.add(MissingInformationRequest(
            candidate_id=candidate_id,
            module_name="education_analysis",
            missing_fields_json=json.dumps(missing_fields),
            draft_email_subject=subject,
            draft_email_body=body,
            status="draft",
        ))


# ---------------------------------------------------------------------------
# Result dataclass returned to the router
# ---------------------------------------------------------------------------
@dataclass
class EducationAnalysisResult:
    candidate_id: int
    records_processed: int
    gaps_detected: int
    gaps_justified: int
    institutions_ranked: int
    education_strength_score: Optional[float]
    progression_assessment: str
    specialization_consistency: str
    performance_trend: str
    strength_summary: str
    missing_fields: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    llm_used: bool = False


# ---------------------------------------------------------------------------
# Main service function
# ---------------------------------------------------------------------------
def run_education_analysis(
    db: Session,
    candidate_id: int,
) -> EducationAnalysisResult:
    """
    Entry point called by the router and by the full-pipeline task.
    Mutates DB rows and returns a structured result.
    """
    logger.info("[EduAnalysis] Starting for candidate_id=%d", candidate_id)

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    records: list[EducationRecord] = (
        db.query(EducationRecord)
        .filter_by(candidate_id=candidate_id)
        .all()
    )
    experiences: list[WorkExperience] = (
        db.query(WorkExperience)
        .filter_by(candidate_id=candidate_id)
        .all()
    )

    if not records:
        logger.warning("[EduAnalysis] No education records for candidate %d", candidate_id)
        return EducationAnalysisResult(
            candidate_id=candidate_id,
            records_processed=0,
            gaps_detected=0,
            gaps_justified=0,
            institutions_ranked=0,
            education_strength_score=None,
            progression_assessment="Insufficient Data",
            specialization_consistency="N/A",
            performance_trend="Insufficient Data",
            strength_summary="No education records found.",
            missing_fields=["All education records missing"],
        )

    # ------------------------------------------------------------------
    # 2. Normalise CGPA and write back to each record
    # ------------------------------------------------------------------
    for rec in records:
        norm = _normalise_cgpa(rec.cgpa, rec.cgpa_scale, rec.marks_percentage)
        if norm is not None:
            rec.normalized_cgpa = norm

    # ------------------------------------------------------------------
    # 3. QS ranking lookup per institution
    # ------------------------------------------------------------------
    qs_lookup = QSRankingLookup.get()
    qs_results: dict[str, dict] = {}
    institutions_ranked = 0

    for rec in records:
        inst = rec.institution
        if not inst or inst in qs_results:
            continue
        result = qs_lookup.lookup(inst)
        if result:
            qs_results[inst] = result
            institutions_ranked += 1
            # Parse rank as int for the column
            raw_rank = result.get("rank_2026", "")
            try:
                rank_int = int(str(raw_rank).lstrip("=").split("-")[0].replace("+", ""))
            except (ValueError, AttributeError):
                rank_int = None
            rec.institution_qs_ranking   = rank_int
            rec.institution_ranking_source = "QS"
            rec.institution_ranking_year  = 2026
            rec.institution_ranking_value = str(raw_rank)
            # Write InstitutionRanking table row
            _upsert_institution_ranking(db, candidate_id, inst, result)

    # ------------------------------------------------------------------
    # 4. Gap detection
    # ------------------------------------------------------------------
    gaps = _detect_education_gaps(records)

    # ------------------------------------------------------------------
    # 5. Gap justification
    # ------------------------------------------------------------------
    gap_justifications: dict[int, tuple[bool, str]] = {}
    justified_count = 0

    for i, gap in enumerate(gaps):
        justified, just_text, work_exp_id = _justify_gap(gap, experiences)
        gap_justifications[i] = (justified, just_text)
        if justified:
            justified_count += 1

        # Write EducationGap row
        _upsert_education_gap(db, candidate_id, gap, justified, just_text, work_exp_id)

    # Write gap_before_start_months and gap_justified_by_experience back to records
    for gap in gaps:
        # Find the record that has to_stage
        for rec in records:
            if rec.stage and rec.stage.lower().strip() == gap.to_stage.lower().strip():
                rec.gap_before_start_months     = gap.gap_months
                for idx, g in enumerate(gaps):
                    if g is gap:
                        j, _ = gap_justifications.get(idx, (False, ""))
                        rec.gap_justified_by_experience = j

    # ------------------------------------------------------------------
    # 6. Missing field detection
    # ------------------------------------------------------------------
    missing_fields = _detect_missing_fields(records)

    # ------------------------------------------------------------------
    # 7. Groq LLM assessment
    # ------------------------------------------------------------------
    user_prompt = _build_education_prompt(records, gaps, gap_justifications, qs_results)
    llm_result = analysis_llm_call(_EDUCATION_SYSTEM_PROMPT, user_prompt, max_tokens=1500)
    llm_used = llm_result is not None and isinstance(llm_result, dict)

    if llm_result:
        edu_score              = float(llm_result.get("education_strength_score", 5.0))
        progression            = llm_result.get("progression_assessment", "Insufficient Data")
        specialization         = llm_result.get("specialization_consistency", "N/A")
        perf_trend             = llm_result.get("performance_trend", "Insufficient Data")
        strength_summary       = llm_result.get("strength_summary", "")
        flags                  = llm_result.get("flags", [])
    else:
        # Fallback: compute a simple heuristic score
        normed_scores = [r.normalized_cgpa for r in records if r.normalized_cgpa]
        avg_normed    = sum(normed_scores) / len(normed_scores) if normed_scores else None
        edu_score     = round((avg_normed / 4.0) * 6.0 + (institutions_ranked * 0.5), 1) if avg_normed else 4.0
        edu_score     = min(max(edu_score, 1.0), 10.0)
        progression   = "Insufficient Data"
        specialization = "N/A"
        perf_trend    = "Insufficient Data"
        strength_summary = "LLM assessment unavailable. Heuristic score computed from normalized CGPA."
        flags         = ["LLM_UNAVAILABLE"]
        llm_result    = {}

    # ------------------------------------------------------------------
    # 8. Write CandidateAssessment
    # ------------------------------------------------------------------
    _upsert_assessment(db, candidate_id, edu_score, strength_summary, llm_result)

    # ------------------------------------------------------------------
    # 9. Missing information email (only if fields are missing)
    # ------------------------------------------------------------------
    if missing_fields:
        from app.models.models import Candidate
        cand = db.query(Candidate).filter_by(id=candidate_id).first()
        cand_name  = cand.name  if cand else "Candidate"
        cand_email = cand.email if cand else None
        subject, body = _generate_missing_info_email(cand_name, cand_email, missing_fields)
        _upsert_missing_info_request(db, candidate_id, missing_fields, subject, body)

    # ------------------------------------------------------------------
    # 10. Commit
    # ------------------------------------------------------------------
    try:
        db.commit()
        logger.info(
            "[EduAnalysis] Done candidate=%d | score=%.1f | gaps=%d | justified=%d | ranked=%d | missing=%d",
            candidate_id, edu_score, len(gaps), justified_count, institutions_ranked, len(missing_fields),
        )
    except Exception as exc:
        db.rollback()
        logger.error("[EduAnalysis] DB commit failed for candidate %d: %s", candidate_id, exc)
        raise

    return EducationAnalysisResult(
        candidate_id=candidate_id,
        records_processed=len(records),
        gaps_detected=len(gaps),
        gaps_justified=justified_count,
        institutions_ranked=institutions_ranked,
        education_strength_score=edu_score,
        progression_assessment=progression,
        specialization_consistency=specialization,
        performance_trend=perf_trend,
        strength_summary=strength_summary,
        missing_fields=missing_fields,
        flags=flags if isinstance(flags, list) else [],
        llm_used=llm_used,
    )
