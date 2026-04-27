"""
analysis_router.py
------------------
FastAPI router for Module 2 analysis endpoints.

Endpoints:
  POST /analysis/education/{candidate_id}      — Run education analysis
  GET  /analysis/education/{candidate_id}       — Read cached education results
  POST /analysis/education/batch                — Batch education analysis

  POST /analysis/experience/{candidate_id}      — Run experience analysis
  GET  /analysis/experience/{candidate_id}      — Read cached experience results
  POST /analysis/experience/batch               — Batch experience analysis

  POST /analysis/summary/{candidate_id}         — Generate candidate summary
  GET  /analysis/summary/{candidate_id}         — Read cached summary
  POST /analysis/summary/batch                  — Batch summary generation

  POST /analysis/full-pipeline/{candidate_id}   — Run all analyses in sequence
  POST /analysis/full-pipeline/batch            — Full pipeline for all candidates

  GET  /analysis/dashboard                      — All candidates with scores
  GET  /analysis/missing-info/{candidate_id}    — Missing info requests
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.models import (
    Candidate,
    CandidateAssessment,
    EducationGap,
    EducationRecord,
    EmploymentGap,
    InstitutionRanking,
    JournalPublication,
    ConferencePublication,
    MissingInformationRequest,
    Skill,
    SupervisionRecord,
    WorkExperience,
)
from app.services.education_analysis import EducationAnalysisResult, run_education_analysis
from app.services.experience_analysis import ExperienceAnalysisResult, run_experience_analysis
from app.services.summary_generator import generate_candidate_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["Module 2 — Analysis"])


# ---------------------------------------------------------------------------
# DB dependency — sync, matches cv_tasks.py pattern
# ---------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class EducationAnalysisResponse(BaseModel):
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
    missing_fields: list[str]
    flags: list[str]
    llm_used: bool

    class Config:
        from_attributes = True


class ExperienceAnalysisResponse(BaseModel):
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
    missing_fields: list[str]
    flags: list[str]
    llm_used: bool

    class Config:
        from_attributes = True


class SummaryResponse(BaseModel):
    candidate_id: int
    overall_rank: Optional[float]
    education_score: Optional[float]
    research_score: Optional[float]
    experience_score: Optional[float]
    skill_score: Optional[float]
    summary: Optional[str]
    llm_used: bool


class BatchRequest(BaseModel):
    candidate_ids: Optional[list[int]] = None   # None = run all


class BatchResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[dict]


class EducationReadResponse(BaseModel):
    candidate_id: int
    education_strength_score: Optional[float]
    gaps: list[dict]
    institution_rankings: list[dict]
    missing_fields: Optional[list[str]]
    strength_summary: Optional[str]


class ExperienceReadResponse(BaseModel):
    candidate_id: int
    experience_strength_score: Optional[float]
    gaps: list[dict]
    total_experience_months: Optional[int]
    academic_experience_months: Optional[int]
    industry_experience_months: Optional[int]
    missing_fields: Optional[list[str]]
    strength_summary: Optional[str]


class SummaryReadResponse(BaseModel):
    candidate_id: int
    name: Optional[str]
    overall_rank: Optional[float]
    education_score: Optional[float]
    research_score: Optional[float]
    experience_score: Optional[float]
    skill_score: Optional[float]
    summary: Optional[str]


class DashboardCandidate(BaseModel):
    candidate_id: int
    name: Optional[str]
    email: Optional[str]
    status: Optional[str]
    education_score: Optional[float]
    experience_score: Optional[float]
    research_score: Optional[float]
    skill_score: Optional[float]
    overall_rank: Optional[float]
    summary: Optional[str]
    education_count: int
    experience_count: int
    journal_count: int
    conference_count: int
    skill_count: int
    supervision_count: int
    missing_info_count: int


class DashboardResponse(BaseModel):
    total_candidates: int
    candidates: list[DashboardCandidate]


class MissingInfoResponse(BaseModel):
    candidate_id: int
    requests: list[dict]


# ===========================================================================
# EDUCATION ENDPOINTS
# ===========================================================================
@router.post(
    "/education/batch",
    response_model=BatchResponse,
    summary="Run educational profile analysis for multiple (or all) candidates",
)
def batch_analyze_education(payload: BatchRequest, db: Session = Depends(get_db)):
    if payload.candidate_ids:
        ids = payload.candidate_ids
    else:
        ids = [row.id for row in db.query(Candidate.id).all()]

    results = []
    succeeded = 0
    failed = 0
    for cid in ids:
        try:
            r = run_education_analysis(db, cid)
            results.append({
                "candidate_id": cid,
                "status": "ok",
                "score": r.education_strength_score,
                "missing_count": len(r.missing_fields),
            })
            succeeded += 1
        except Exception as exc:
            results.append({"candidate_id": cid, "status": "error", "detail": str(exc)})
            failed += 1

    return BatchResponse(total=len(ids), succeeded=succeeded, failed=failed, results=results)


@router.post(
    "/education/{candidate_id}",
    response_model=EducationAnalysisResponse,
    summary="Run educational profile analysis for one candidate",
)
def analyze_education(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter_by(id=candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    try:
        result: EducationAnalysisResult = run_education_analysis(db, candidate_id)
    except Exception as exc:
        logger.exception("Education analysis failed for candidate %d: %s", candidate_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return EducationAnalysisResponse(
        candidate_id=result.candidate_id,
        records_processed=result.records_processed,
        gaps_detected=result.gaps_detected,
        gaps_justified=result.gaps_justified,
        institutions_ranked=result.institutions_ranked,
        education_strength_score=result.education_strength_score,
        progression_assessment=result.progression_assessment,
        specialization_consistency=result.specialization_consistency,
        performance_trend=result.performance_trend,
        strength_summary=result.strength_summary,
        missing_fields=result.missing_fields,
        flags=result.flags,
        llm_used=result.llm_used,
    )


@router.get(
    "/education/{candidate_id}",
    response_model=EducationReadResponse,
    summary="Read cached educational analysis for one candidate",
)
def get_education_analysis(candidate_id: int, db: Session = Depends(get_db)):
    assessment = (
        db.query(CandidateAssessment)
        .filter_by(candidate_id=candidate_id)
        .order_by(CandidateAssessment.generated_at.desc())
        .first()
    )
    gaps = db.query(EducationGap).filter_by(candidate_id=candidate_id).all()
    rankings = db.query(InstitutionRanking).filter_by(candidate_id=candidate_id).all()
    missing_req = (
        db.query(MissingInformationRequest)
        .filter_by(candidate_id=candidate_id, module_name="education_analysis")
        .first()
    )

    return EducationReadResponse(
        candidate_id=candidate_id,
        education_strength_score=assessment.education_strength_score if assessment else None,
        strength_summary=assessment.overall_summary if assessment else None,
        gaps=[
            {
                "from_stage":       g.from_stage,
                "to_stage":         g.to_stage,
                "gap_months":       g.gap_months,
                "justified":        g.justified_by_work,
                "justification":    g.justification_text,
            }
            for g in gaps
        ],
        institution_rankings=[
            {
                "institution": r.institution_name,
                "source":      r.source,
                "rank":        r.rank_value,
                "country":     r.country,
            }
            for r in rankings
        ],
        missing_fields=(
            json.loads(missing_req.missing_fields_json)
            if missing_req and missing_req.missing_fields_json
            else []
        ),
    )


# ===========================================================================
# EXPERIENCE ENDPOINTS
# ===========================================================================
@router.post(
    "/experience/batch",
    response_model=BatchResponse,
    summary="Run experience analysis for multiple (or all) candidates",
)
def batch_analyze_experience(payload: BatchRequest, db: Session = Depends(get_db)):
    if payload.candidate_ids:
        ids = payload.candidate_ids
    else:
        ids = [row.id for row in db.query(Candidate.id).all()]

    results = []
    succeeded = 0
    failed = 0
    for cid in ids:
        try:
            r = run_experience_analysis(db, cid)
            results.append({
                "candidate_id": cid,
                "status": "ok",
                "score": r.experience_strength_score,
                "missing_count": len(r.missing_fields),
            })
            succeeded += 1
        except Exception as exc:
            results.append({"candidate_id": cid, "status": "error", "detail": str(exc)})
            failed += 1

    return BatchResponse(total=len(ids), succeeded=succeeded, failed=failed, results=results)


@router.post(
    "/experience/{candidate_id}",
    response_model=ExperienceAnalysisResponse,
    summary="Run experience analysis for one candidate",
)
def analyze_experience(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter_by(id=candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    try:
        result: ExperienceAnalysisResult = run_experience_analysis(db, candidate_id)
    except Exception as exc:
        logger.exception("Experience analysis failed for candidate %d: %s", candidate_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return ExperienceAnalysisResponse(
        candidate_id=result.candidate_id,
        records_processed=result.records_processed,
        total_experience_months=result.total_experience_months,
        academic_experience_months=result.academic_experience_months,
        industry_experience_months=result.industry_experience_months,
        gaps_detected=result.gaps_detected,
        gaps_justified=result.gaps_justified,
        experience_strength_score=result.experience_strength_score,
        career_progression=result.career_progression,
        role_diversity=result.role_diversity,
        strength_summary=result.strength_summary,
        missing_fields=result.missing_fields,
        flags=result.flags,
        llm_used=result.llm_used,
    )


@router.get(
    "/experience/{candidate_id}",
    response_model=ExperienceReadResponse,
    summary="Read cached experience analysis for one candidate",
)
def get_experience_analysis(candidate_id: int, db: Session = Depends(get_db)):
    assessment = (
        db.query(CandidateAssessment)
        .filter_by(candidate_id=candidate_id)
        .order_by(CandidateAssessment.generated_at.desc())
        .first()
    )
    gaps = db.query(EmploymentGap).filter_by(candidate_id=candidate_id).all()
    missing_req = (
        db.query(MissingInformationRequest)
        .filter_by(candidate_id=candidate_id, module_name="experience_analysis")
        .first()
    )

    # Compute totals from work experiences
    experiences = db.query(WorkExperience).filter_by(candidate_id=candidate_id).all()
    total_months = 0
    academic_months = 0
    industry_months = 0
    from app.services.experience_analysis import _exp_start_date, _exp_end_date, _months_between
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

    return ExperienceReadResponse(
        candidate_id=candidate_id,
        experience_strength_score=assessment.experience_strength_score if assessment else None,
        strength_summary=assessment.overall_summary if assessment else None,
        total_experience_months=total_months,
        academic_experience_months=academic_months,
        industry_experience_months=industry_months,
        gaps=[
            {
                "gap_type":         g.gap_type,
                "gap_months":       g.gap_months,
                "gap_start":        str(g.gap_start) if g.gap_start else None,
                "gap_end":          str(g.gap_end) if g.gap_end else None,
                "justified":        g.justified,
                "justification":    g.justification_text,
            }
            for g in gaps
        ],
        missing_fields=(
            json.loads(missing_req.missing_fields_json)
            if missing_req and missing_req.missing_fields_json
            else []
        ),
    )


# ===========================================================================
# SUMMARY ENDPOINTS
# ===========================================================================
@router.post(
    "/summary/batch",
    response_model=BatchResponse,
    summary="Generate summaries for multiple (or all) candidates",
)
def batch_generate_summary(payload: BatchRequest, db: Session = Depends(get_db)):
    if payload.candidate_ids:
        ids = payload.candidate_ids
    else:
        ids = [row.id for row in db.query(Candidate.id).all()]

    results = []
    succeeded = 0
    failed = 0
    for cid in ids:
        try:
            r = generate_candidate_summary(db, cid)
            results.append({
                "candidate_id": cid,
                "status": "ok",
                "overall_rank": r["overall_rank"],
            })
            succeeded += 1
        except Exception as exc:
            results.append({"candidate_id": cid, "status": "error", "detail": str(exc)})
            failed += 1

    return BatchResponse(total=len(ids), succeeded=succeeded, failed=failed, results=results)


@router.post(
    "/summary/{candidate_id}",
    response_model=SummaryResponse,
    summary="Generate candidate summary and overall rank",
)
def create_summary(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter_by(id=candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    try:
        result = generate_candidate_summary(db, candidate_id)
    except Exception as exc:
        logger.exception("Summary generation failed for candidate %d: %s", candidate_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return SummaryResponse(
        candidate_id=candidate_id,
        overall_rank=result["overall_rank"],
        education_score=result["education_score"],
        research_score=result["research_score"],
        experience_score=result["experience_score"],
        skill_score=result["skill_score"],
        summary=result["summary"],
        llm_used=result["llm_used"],
    )


@router.get(
    "/summary/{candidate_id}",
    response_model=SummaryReadResponse,
    summary="Read cached candidate summary",
)
def get_summary(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter_by(id=candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    assessment = (
        db.query(CandidateAssessment)
        .filter_by(candidate_id=candidate_id)
        .order_by(CandidateAssessment.generated_at.desc())
        .first()
    )

    return SummaryReadResponse(
        candidate_id=candidate_id,
        name=candidate.name,
        overall_rank=assessment.overall_rank if assessment else None,
        education_score=assessment.education_strength_score if assessment else None,
        research_score=assessment.research_strength_score if assessment else None,
        experience_score=assessment.experience_strength_score if assessment else None,
        skill_score=assessment.skill_alignment_score if assessment else None,
        summary=candidate.summary,
    )


# ===========================================================================
# FULL PIPELINE
# ===========================================================================
@router.post(
    "/full-pipeline/batch",
    response_model=BatchResponse,
    summary="Run full analysis pipeline (education + experience + summary) for all candidates",
)
def batch_full_pipeline(payload: BatchRequest, db: Session = Depends(get_db)):
    if payload.candidate_ids:
        ids = payload.candidate_ids
    else:
        ids = [row.id for row in db.query(Candidate.id).all()]

    results = []
    succeeded = 0
    failed = 0
    for cid in ids:
        try:
            edu_result = run_education_analysis(db, cid)
            exp_result = run_experience_analysis(db, cid)
            summary_result = generate_candidate_summary(db, cid)
            results.append({
                "candidate_id": cid,
                "status": "ok",
                "education_score": edu_result.education_strength_score,
                "experience_score": exp_result.experience_strength_score,
                "overall_rank": summary_result["overall_rank"],
            })
            succeeded += 1
        except Exception as exc:
            logger.exception("Full pipeline failed for candidate %d", cid)
            results.append({"candidate_id": cid, "status": "error", "detail": str(exc)})
            failed += 1

    return BatchResponse(total=len(ids), succeeded=succeeded, failed=failed, results=results)


@router.post(
    "/full-pipeline/{candidate_id}",
    response_model=SummaryResponse,
    summary="Run full analysis pipeline for one candidate",
)
def full_pipeline(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter_by(id=candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    try:
        run_education_analysis(db, candidate_id)
        run_experience_analysis(db, candidate_id)
        result = generate_candidate_summary(db, candidate_id)
    except Exception as exc:
        logger.exception("Full pipeline failed for candidate %d: %s", candidate_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return SummaryResponse(
        candidate_id=candidate_id,
        overall_rank=result["overall_rank"],
        education_score=result["education_score"],
        research_score=result["research_score"],
        experience_score=result["experience_score"],
        skill_score=result["skill_score"],
        summary=result["summary"],
        llm_used=result["llm_used"],
    )


# ===========================================================================
# DASHBOARD
# ===========================================================================
@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get all candidates with analysis scores for dashboard view",
)
def get_dashboard(db: Session = Depends(get_db)):
    candidates = db.query(Candidate).all()

    dashboard_candidates = []
    for cand in candidates:
        assessment = (
            db.query(CandidateAssessment)
            .filter_by(candidate_id=cand.id)
            .order_by(CandidateAssessment.generated_at.desc())
            .first()
        )
        missing_count = (
            db.query(MissingInformationRequest)
            .filter_by(candidate_id=cand.id)
            .count()
        )

        dashboard_candidates.append(DashboardCandidate(
            candidate_id=cand.id,
            name=cand.name,
            email=cand.email,
            status=cand.status,
            education_score=assessment.education_strength_score if assessment else None,
            experience_score=assessment.experience_strength_score if assessment else None,
            research_score=assessment.research_strength_score if assessment else None,
            skill_score=assessment.skill_alignment_score if assessment else None,
            overall_rank=assessment.overall_rank if assessment else None,
            summary=cand.summary,
            education_count=len(cand.education_records),
            experience_count=len(cand.work_experiences),
            journal_count=len(cand.journal_publications),
            conference_count=len(cand.conference_publications),
            skill_count=len(cand.skills),
            supervision_count=len(cand.supervision_records),
            missing_info_count=missing_count,
        ))

    return DashboardResponse(
        total_candidates=len(dashboard_candidates),
        candidates=dashboard_candidates,
    )


# ===========================================================================
# MISSING INFO
# ===========================================================================
@router.get(
    "/missing-info/{candidate_id}",
    response_model=MissingInfoResponse,
    summary="Get all missing information requests for a candidate",
)
def get_missing_info(candidate_id: int, db: Session = Depends(get_db)):
    requests = (
        db.query(MissingInformationRequest)
        .filter_by(candidate_id=candidate_id)
        .all()
    )

    return MissingInfoResponse(
        candidate_id=candidate_id,
        requests=[
            {
                "id": r.id,
                "module_name": r.module_name,
                "missing_fields": json.loads(r.missing_fields_json) if r.missing_fields_json else [],
                "draft_email_subject": r.draft_email_subject,
                "draft_email_body": r.draft_email_body,
                "status": r.status,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            }
            for r in requests
        ],
    )


# ===========================================================================
# RESEARCH ANALYSIS  (Phase B)
# ===========================================================================
from app.services.research_analysis import ResearchAnalysisResult, run_research_analysis


class ResearchAnalysisResponse(BaseModel):
    candidate_id: int
    grade: str
    final_score: float
    normalized_score: float
    base_score: float
    components: dict
    bonus_breakdown: dict
    counts: dict
    warnings: list[str]
    recommendations: list[str]

    class Config:
        from_attributes = True


@router.post(
    "/research/{candidate_id}",
    response_model=ResearchAnalysisResponse,
    summary="Run research profile analysis for one candidate",
)
def analyze_research(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter_by(id=candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")
    try:
        result: ResearchAnalysisResult = run_research_analysis(db, candidate_id)
    except Exception as exc:
        logger.exception("Research analysis failed for candidate %d: %s", candidate_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return ResearchAnalysisResponse(
        candidate_id=result.candidate_id,
        grade=result.grade,
        final_score=result.final_score,
        normalized_score=result.normalized_score,
        base_score=result.base_score,
        components=result.components,
        bonus_breakdown=result.bonus_breakdown,
        counts=result.counts,
        warnings=result.warnings,
        recommendations=result.recommendations,
    )


@router.get(
    "/research/{candidate_id}",
    response_model=ResearchAnalysisResponse,
    summary="Read cached research analysis for one candidate",
)
def get_research_analysis(candidate_id: int, db: Session = Depends(get_db)):
    assessment = (
        db.query(CandidateAssessment)
        .filter_by(candidate_id=candidate_id)
        .order_by(CandidateAssessment.generated_at.desc())
        .first()
    )
    if not assessment or assessment.research_strength_score is None:
        raise HTTPException(
            status_code=404,
            detail="No research analysis found — run POST /analysis/research/{id} first",
        )
    return ResearchAnalysisResponse(
        candidate_id=candidate_id,
        grade="CACHED",
        final_score=assessment.research_strength_score or 0.0,
        normalized_score=assessment.research_strength_score or 0.0,
        base_score=0.0,
        components={},
        bonus_breakdown={},
        counts={},
        warnings=[],
        recommendations=[],
    )


@router.post(
    "/research/batch",
    response_model=BatchResponse,
    summary="Run research analysis for multiple (or all) candidates",
)
def batch_analyze_research(payload: BatchRequest, db: Session = Depends(get_db)):
    ids = payload.candidate_ids or [row.id for row in db.query(Candidate.id).all()]
    results, succeeded, failed = [], 0, 0
    for cid in ids:
        try:
            r = run_research_analysis(db, cid)
            results.append({
                "candidate_id": cid,
                "status": "ok",
                "grade": r.grade,
                "final_score": r.final_score,
            })
            succeeded += 1
        except Exception as exc:
            results.append({"candidate_id": cid, "status": "error", "detail": str(exc)})
            failed += 1
    return BatchResponse(total=len(ids), succeeded=succeeded, failed=failed, results=results)
