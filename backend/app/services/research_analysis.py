"""
research_analysis.py
--------------------
Updates candidate publications using authoritative QS/CORE/Scimago data,
then calculates the true research strength score.
"""
import logging
from sqlalchemy.orm import Session
from app.models.models import CandidateAssessment, JournalPublication, ConferencePublication, SupervisionRecord
from app.services.research_lookup import ScimagoLookup, CoreLookup

logger = logging.getLogger(__name__)

def run_research_analysis(db: Session, candidate_id: int) -> None:
    """
    1. Looks up all journals in Scimago and overwrites 'quartile'.
    2. Looks up all conferences in CORE and overwrites 'core_ranking'.
    3. Calculates a precise research score based on authoritative rankings.
    4. Saves to CandidateAssessment.
    """
    logger.info("[ResearchAnalysis] Starting for candidate_id=%d", candidate_id)
    
    journals = db.query(JournalPublication).filter_by(candidate_id=candidate_id).all()
    conferences = db.query(ConferencePublication).filter_by(candidate_id=candidate_id).all()
    supervisions = db.query(SupervisionRecord).filter_by(candidate_id=candidate_id).all()
    
    scimago = ScimagoLookup.get()
    core = CoreLookup.get()
    
    # 1. Authoritative Journal Lookup
    for j in journals:
        match = scimago.lookup(j.journal_name or j.title)
        if match:
            j.quartile = match["quartile"]
            logger.info("  [Journal Match] '%s' -> %s", j.journal_name, match["quartile"])
        else:
            j.quartile = "Unranked"

    # 2. Authoritative Conference Lookup
    for c in conferences:
        # Pass the conference name (or series as acronym)
        match = core.lookup(c.conference_name or c.title, acronym=c.conference_series)
        if match:
            # Re-map rank to our Enum exactly
            raw_rank = match["rank"].strip().upper()
            if raw_rank == "A*": c.core_ranking = "A*"
            elif raw_rank == "A": c.core_ranking = "A"
            elif raw_rank == "B": c.core_ranking = "B"
            elif raw_rank == "C": c.core_ranking = "C"
            else: c.core_ranking = "Unranked"
            logger.info("  [Conference Match] '%s' -> %s", c.conference_name, c.core_ranking)
        else:
            c.core_ranking = "Unranked"

    # 3. Calculate Research Score using HR Weights
    score = 0.0
    
    # Journals: Q1 = 1.5, Q2 = 1.0, Q3 = 0.5, Q4 = 0.2
    for j in journals:
        q = (j.quartile or "").upper()
        if q == "Q1": score += 1.5
        elif q == "Q2": score += 1.0
        elif q == "Q3": score += 0.5
        elif q == "Q4": score += 0.2
        else: score += 0.1
        
    # Conferences: A* = 1.5, A = 1.0, B = 0.5, C = 0.2
    for c in conferences:
        r = (c.core_ranking or "").upper()
        if r == "A*": score += 1.5
        elif r == "A": score += 1.0
        elif r == "B": score += 0.5
        elif r == "C": score += 0.2
        else: score += 0.1
        
    # Supervision: 0.5 per student
    score += len(supervisions) * 0.5
    
    # Normalize to 10
    final_score = round(min(score, 10.0), 1)
    
    # 4. Save
    assessment = (
        db.query(CandidateAssessment)
        .filter_by(candidate_id=candidate_id)
        .order_by(CandidateAssessment.generated_at.desc())
        .first()
    )
    if assessment:
        assessment.research_strength_score = final_score
    else:
        db.add(CandidateAssessment(
            candidate_id=candidate_id,
            assessment_version="m2_research",
            research_strength_score=final_score,
        ))
        
    db.commit()
    logger.info("[ResearchAnalysis] Completed candidate=%d | Final Score: %.1f", candidate_id, final_score)
