"""Script to append research router endpoints to analysis_router.py"""
from pathlib import Path

APPEND_CONTENT = '''

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
'''

target = Path("/home/mhamd/talashv3/backend/app/routers/analysis_router.py")

# Check not already appended
existing = target.read_text(encoding="utf-8")
if "analyze_research" in existing:
    print("Already appended — skipping.")
else:
    with open(target, "a", encoding="utf-8") as f:
        f.write(APPEND_CONTENT)
    print("Appended research endpoints successfully.")
