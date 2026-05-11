"""
research_analysis.py
--------------------
Main research scoring service. Entry point: run_research_analysis(db, candidate_id).
Mirrors the pattern of education_analysis.py exactly.

Scoring breakdown (v2.0):
  Base components (max 82):
    - Publication Quality  : 35
    - Authorship Strength  : 20
    - Collaboration        : 15
    - Conference Maturity  : 12
    - Supervision Record   :  8
  Normalized to 100: (base / 82) * 100
  Bonuses (added after normalization):
    - Has any books   : +5
    - Has any patents  : +5
  Final: 0–110 (grade assigned on final)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import (
    Book,
    CandidateAssessment,
    Candidate,
    ConferencePublication,
    JournalPublication,
    Patent,
    SupervisionRecord,
)
from app.utils.scores import research_strength_for_persist

from app.services.scimago_lookup import ScimagoLookup
from app.services.core_lookup import CoreLookup
from app.services.research_enrichment import (
    _is_generic_venue,
    detect_conference_indexing,
    enrich_all_publications,
)
from app.services.sync_async import run_coro_sync

logger = logging.getLogger(__name__)

CURRENT_YEAR = 2026


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class ResearchAnalysisResult:
    candidate_id: int
    final_score: float          # 0–110
    normalized_score: float     # 0–100 before bonuses
    base_score: float           # 0–82 raw
    grade: str
    components: dict
    bonus_breakdown: dict
    counts: dict
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    enrichment_audit: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def _norm_role(role_str: str) -> str:
    role = (role_str or "").lower().strip()
    mapping = {
        "first": "first_author",
        "first_author": "first_author",
        "first author": "first_author",
        "corresponding": "corresponding_author",
        "corresponding_author": "corresponding_author",
        "corresponding author": "corresponding_author",
        "first_and_corresponding": "first_and_corresponding",
        "first and corresponding": "first_and_corresponding",
        "first_corresponding": "first_and_corresponding",
        "co_author": "co_author",
        "co-author": "co_author",
        "co author": "co_author",
        "coauthor": "co_author",
    }
    return mapping.get(role, "unknown")


def _extract_ordinal(*text_parts: str) -> Optional[str]:
    """Parse edition like '13th Annual' or '28th IEEE' from venue and/or title."""
    blob = " ".join(p for p in text_parts if p).strip()
    if not blob:
        return None
    m = re.search(r"\b(\d{1,3})\s*(st|nd|rd|th)\b", blob, re.I)
    if m:
        return f"{m.group(1)}{m.group(2).lower()}"
    return None


def _build_maturity(ordinal: Optional[str], earliest_year: Optional[int]) -> dict:
    result = {"ordinal_edition": ordinal, "earliest_year": earliest_year,
               "age_years": None, "maturity_label": "unknown"}
    if earliest_year:
        age = CURRENT_YEAR - earliest_year
        result["age_years"] = age
        if age >= 20:   result["maturity_label"] = f"Mature ({age}+ yrs, est. {earliest_year})"
        elif age >= 10: result["maturity_label"] = f"Established ({age} yrs, est. {earliest_year})"
        elif age >= 5:  result["maturity_label"] = f"Growing ({age} yrs, est. {earliest_year})"
        else:           result["maturity_label"] = f"Newer venue ({age} yrs, est. {earliest_year})"
        return result
    if ordinal:
        nm = re.search(r"\d+", ordinal)
        if nm:
            num = int(nm.group()); age = num - 1
            result["age_years"] = age
            if num >= 20:   result["maturity_label"] = f"Mature series ({ordinal} ed.)"
            elif num >= 10: result["maturity_label"] = f"Established series ({ordinal} ed.)"
            elif num >= 5:  result["maturity_label"] = f"Growing series ({ordinal} ed.)"
            else:           result["maturity_label"] = f"Newer series ({ordinal} ed.)"
        return result
    result["maturity_label"] = "Maturity unresolvable"
    return result


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def _score_publication_quality(j_pubs: list[dict], c_pubs: list[dict]) -> dict:
    MAX = 35
    reasons, warnings, scores = [], [], []

    for p in j_pubs:
        q = str(p.get("quartile") or "").strip().upper()
        q = q if q in ("Q1", "Q2", "Q3", "Q4") else None
        wos = p.get("wos_indexed") or False
        sc = p.get("scopus_indexed") or p.get("oa_scopus_proxy") or False
        title = (p.get("title") or "Untitled")[:55]
        tier = str(p.get("openalex_journal_tier") or "weak").lower()
        doaj = bool(p.get("doaj_indexed"))

        if q == "Q1" and wos:
            pts, note = 8.0, "Q1+WoS"
        elif q == "Q1" and sc:
            pts, note = 7.0, "Q1+Scopus"
        elif q == "Q1":
            pts, note = 5.5, "Q1 (indexing unverified)"
        elif q == "Q2" and (wos or sc):
            pts, note = 5.0, "Q2+indexed"
        elif q == "Q2":
            pts, note = 4.0, "Q2 (indexing unverified)"
        elif q == "Q3" and (wos or sc):
            pts, note = 3.0, "Q3+indexed"
        elif q == "Q3":
            pts, note = 2.0, "Q3 (indexing unverified)"
        elif q == "Q4":
            pts, note = 1.0, "Q4"
        elif doaj and tier == "strong":
            pts, note = 3.0, "DOAJ + strong OpenAlex venue (no Scimago quartile)"
        elif doaj and tier in ("medium", "modest"):
            pts, note = 2.5, "DOAJ + moderate OpenAlex venue"
        elif doaj:
            pts, note = 2.1, "DOAJ listed journal"
        elif tier == "strong" and (wos or sc):
            pts, note = 3.2, "Strong OpenAlex venue + indexing signal"
        elif tier == "strong":
            pts, note = 2.7, "Strong OpenAlex venue (Scimago quartile unavailable)"
        elif tier == "medium" and (wos or sc):
            pts, note = 2.4, "Medium OpenAlex venue + indexing"
        elif tier == "medium":
            pts, note = 2.0, "Medium OpenAlex venue"
        elif tier == "modest":
            pts, note = 1.3, "Modest OpenAlex venue"
        elif p.get("is_legitimate"):
            pts, note = 1.5, "Unranked but verified (Crossref/ISSN)"
        else:
            pts, note = 0.5, "Unranked/unverified"

        scores.append(pts)
        reasons.append(f"Journal '{title}': {pts}pts [{note}]")

    for p in c_pubs:
        rank  = str(p.get("core_ranking") or "").strip().upper()
        proc  = str(p.get("publisher") or "").upper()
        title = (p.get("title") or "Unknown")[:55]
        known = ["IEEE", "ACM", "SPRINGER", "ELSEVIER", "WILEY"]

        if   rank == "A*":                            pts, note = 8.0, "A* CORE"
        elif rank == "A":                             pts, note = 7.0, "A CORE"
        elif rank == "B":                             pts, note = 5.0, "B CORE"
        elif rank == "C":                             pts, note = 2.0, "C CORE"
        elif any(k in proc for k in known):           pts, note = 2.5, f"{proc} publisher"
        else:                                         pts, note = 0.5, "Unranked/unknown"

        scores.append(pts)
        reasons.append(f"Conf '{title}': {pts}pts [{note}]")

    raw = sum(scores)
    final = min(raw, MAX)
    if raw > MAX:
        reasons.append(f"Capped at {MAX} (raw={raw:.1f})")
    reasons.append(f"{len(j_pubs)} journal + {len(c_pubs)} conf papers")
    return {"score": round(final, 1), "max": MAX, "reasons": reasons, "warnings": warnings}


def _score_authorship(j_pubs: list[dict], c_pubs: list[dict]) -> dict:
    MAX = 20
    ROLE_PTS = {
        "first_and_corresponding": 5.0,
        "first_author":            4.0,
        "corresponding_author":    3.0,
        "co_author":               1.0,
        "unknown":                 2.0,
    }
    reasons, warnings = [], []
    role_counts: dict[str, int] = {}
    total_pts = 0.0
    all_pubs = j_pubs + c_pubs

    for p in all_pubs:
        # Prefer API-detected role; fall back to DB-stored role
        raw_role = p.get("authorship_role_api") or p.get("authorship_role") or "unknown"
        role = _norm_role(raw_role)
        pts  = ROLE_PTS.get(role, 1.0)
        total_pts += pts
        role_counts[role] = role_counts.get(role, 0) + 1
        if role == "unknown":
            warnings.append(f"'{(p.get('title') or '')[:40]}': authorship unverified")

    n = len(all_pubs)
    bonus, bonus_reason = 0.0, ""
    if n > 0:
        fa = role_counts.get("first_author", 0) + role_counts.get("first_and_corresponding", 0)
        r  = fa / n
        if   r == 1.0: bonus, bonus_reason = 3.0, f"All {n} papers as first author (+3)"
        elif r >= 0.6: bonus, bonus_reason = 2.0, f"{fa}/{n} as first author (+2)"
        elif r >= 0.3: bonus, bonus_reason = 1.0, f"{fa}/{n} as first author (+1)"

    raw = total_pts + bonus
    final = min(raw, MAX)
    for role, count in sorted(role_counts.items()):
        pts = ROLE_PTS.get(role, 1.0)
        note = " [unverified]" if role == "unknown" else ""
        reasons.append(f"{count}× {role.replace('_',' ').title()} = {count*pts:.0f}pts{note}")
    if bonus > 0:
        reasons.append(bonus_reason)
    if raw > MAX:
        reasons.append(f"Capped at {MAX}")
    return {"score": round(final, 1), "max": MAX, "reasons": reasons, "warnings": warnings}


def _score_collaboration(j_pubs: list[dict], c_pubs: list[dict], candidate_name: str) -> dict:
    MAX = 15
    all_pubs = j_pubs + c_pubs
    if not all_pubs:
        return {"score": 2.0, "max": MAX,
                "reasons": ["No publications — grace 2pts"],
                "warnings": ["No publication data"]}

    cand_last = (candidate_name or "").lower().split()[-1] if candidate_name else ""
    all_co: set[str] = set()
    for p in all_pubs:
        for a in re.split(r"[;,]", p.get("authors") or ""):
            a = a.strip()
            if a and not (cand_last and cand_last in a.lower()):
                all_co.add(a.lower())

    unique_co = len(all_co)
    totals = [len([a for a in re.split(r"[;,]", p.get("authors") or "") if a.strip()])
              for p in all_pubs]
    avg_authors = sum(totals) / len(totals) if totals else 1

    has_intl = any(len([a for a in re.split(r"[;,]", p.get("authors") or "") if a.strip()]) >= 5
                   for p in all_pubs)

    if   unique_co >= 10: base, label = 13.0, "High"
    elif unique_co >= 6:  base, label = 10.0, "Good"
    elif unique_co >= 3:  base, label = 7.0,  "Moderate"
    elif unique_co >= 1:  base, label = 4.0,  "Limited"
    else:                 base, label = 2.0,  "Solo/minimal"

    intl_bonus = 2.0 if has_intl else 0.0
    raw = base + intl_bonus
    final = min(raw, MAX)
    reasons = [f"{label} collaboration: {unique_co} co-authors, avg {avg_authors:.1f}/paper"]
    if has_intl:
        reasons.append("Large author group detected (+2pts)")
    if raw > MAX:
        reasons.append(f"Capped at {MAX}")
    return {"score": round(final, 1), "max": MAX, "reasons": reasons, "warnings": []}


def _score_conference_maturity(c_pubs: list[dict]) -> dict:
    MAX = 12
    if not c_pubs:
        return {"score": 0.0, "max": MAX,
                "reasons": ["No conference papers — 0pts"], "warnings": []}
    MATURITY_PTS = {
        "mature": 2.5, "established": 2.0, "growing": 1.5, "newer": 1.0, "unknown": 1.5,
    }
    reasons, warnings = [], []
    total = 0.0
    for p in c_pubs:
        venue = (p.get("conference_name") or "Unknown")[:55]
        mat   = p.get("maturity") or {}
        label = str(mat.get("maturity_label") or "").lower()
        cat   = next((k for k in MATURITY_PTS if k in label), "unknown")
        if cat == "unknown":
            warnings.append(f"'{venue}': maturity unknown")
        pts = MATURITY_PTS[cat]
        total += pts
        reasons.append(f"'{venue}': {label or 'unknown'} → {pts}pts")
    final = min(total, MAX)
    if total > MAX:
        reasons.append(f"Capped at {MAX}")
    return {"score": round(final, 1), "max": MAX, "reasons": reasons, "warnings": warnings}


def _score_supervision(sup_records: list) -> dict:
    MAX = 8
    LEVEL_PTS = {
        "phd": 1.5, "doctorate": 1.5,
        "ms": 1.0, "mphil": 1.0, "msc": 1.0, "postgrad": 1.0,
        "undergrad": 0.5, "bs": 0.5, "bsc": 0.5, "honors": 0.5,
    }
    if not sup_records:
        return {"score": 0.0, "max": MAX,
                "reasons": ["No supervision records — 0pts"],
                "warnings": ["No supervised students in database"]}
    reasons, total = [], 0.0
    level_counts: dict[str, int] = {}
    for s in sup_records:
        lvl = str(s.get("student_level") or "").lower().strip()
        pts = LEVEL_PTS.get(lvl, 0.5)
        total += pts
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
    for lvl, cnt in sorted(level_counts.items()):
        pts = LEVEL_PTS.get(lvl, 0.5)
        reasons.append(f"{cnt}× {lvl.upper()} = {cnt*pts:.1f}pts")
    final = min(total, MAX)
    if total > MAX:
        reasons.append(f"Capped at {MAX}")
    return {"score": round(final, 1), "max": MAX, "reasons": reasons, "warnings": []}


def _score_patents_books(patents: list, books: list) -> dict:
    MAX = 10
    reasons, warnings, total = [], [], 0.0
    for pat in (patents or []):
        num = (pat.get("patent_no") or "").strip()
        if num:
            total += 5.0; reasons.append(f"Granted patent '{num}': 5pts")
        else:
            total += 2.0; reasons.append("Patent (pending/no number): 2pts")
            warnings.append("Patent number missing — treated as pending")
    for book in (books or []):
        role = str(book.get("authorship_role") or "").lower()
        if "author" in role and "co" not in role:
            total += 6.0; reasons.append("Authored book: 6pts")
        elif "edit" in role or "co" in role:
            total += 4.0; reasons.append("Edited/co-authored book: 4pts")
        elif "chapter" in role:
            total += 2.0; reasons.append("Book chapter: 2pts")
        else:
            total += 2.0; reasons.append("Book (role unspecified): 2pts")
            warnings.append("Book authorship role not specified")
    if not patents and not books:
        reasons.append("No patents or books — 0pts")
    return {"score": round(min(total, MAX), 1), "max": MAX, "reasons": reasons, "warnings": warnings}


def _build_recommendations(components: dict, j_pubs: list, c_pubs: list) -> list[str]:
    recs = []
    if components.get("publication_quality", {}).get("score", 0) < 21:
        recs.append("Target Q1/Q2 Scopus-indexed journals to improve publication quality")
    missing_doi = sum(1 for p in j_pubs + c_pubs if not p.get("doi"))
    if missing_doi:
        recs.append(f"Add DOIs for {missing_doi} publication(s) — improves authorship detection")
    if components.get("authorship_strength", {}).get("score", 0) < 12:
        recs.append("Increase first-author publications to demonstrate research leadership")
    if not c_pubs:
        recs.append("Consider publishing in A/B-ranked CORE conferences")
    elif components.get("conference_maturity", {}).get("score", 0) < 4.8:
        recs.append("Target established/mature conference series (10+ year history)")
    if components.get("supervision_record", {}).get("score", 0) == 0:
        recs.append("Document supervised students (PhD/MS/BS) in the database")
    if components.get("patents_books", {}).get("score", 0) == 0:
        recs.append("Document patents or book chapters if available")
    if components.get("research_collaboration", {}).get("score", 0) < 7.5:
        recs.append("Expand collaboration network — especially international partners")
    return recs


# ---------------------------------------------------------------------------
# DB upsert helper
# ---------------------------------------------------------------------------
def _canonical_authorship_role(raw: str | None) -> Optional[str]:
    if not raw or str(raw).strip().lower() in ("unknown", ""):
        return None
    key = str(raw).strip().lower()
    mapping = {
        "first_author": "First Author",
        "corresponding_author": "Corresponding Author",
        "first_and_corresponding": "Both First and Corresponding Author",
        "co_author": "Other Co-Author",
    }
    return mapping.get(key)


def _persist_enriched_publications(db: Session, j_pubs: list[dict], c_pubs: list[dict]) -> None:
    """Persist recovered metadata to ORM rows (dashboard + CSV exports stay aligned with scoring)."""
    for p in j_pubs:
        jid = p.get("id")
        if not jid:
            continue
        row = db.query(JournalPublication).filter_by(id=jid).first()
        if not row:
            continue
        if p.get("issn"):
            row.issn = p["issn"]
        if p.get("doi"):
            row.doi = p["doi"]
        ven = (p.get("venue") or "").strip()
        if ven and (_is_generic_venue(row.journal_name or "") or not (row.journal_name or "").strip()):
            row.journal_name = ven
        yr = p.get("year")
        if yr is not None and row.year is None:
            try:
                row.year = int(yr)
            except (TypeError, ValueError):
                pass
        if p.get("quartile"):
            row.quartile = p["quartile"]
        if p.get("impact_factor") is not None:
            try:
                row.impact_factor = float(p["impact_factor"])
            except (TypeError, ValueError):
                pass
        if p.get("wos_indexed") is not None:
            row.wos_indexed = bool(p.get("wos_indexed"))
        sc_val = p.get("scopus_indexed")
        if sc_val is None:
            sc_val = p.get("oa_scopus_proxy")
        if sc_val is not None:
            row.scopus_indexed = bool(sc_val)
        role = _canonical_authorship_role(p.get("authorship_role_api"))
        if role:
            row.authorship_role = role

    for p in c_pubs:
        cid_pub = p.get("id")
        if not cid_pub:
            continue
        row = db.query(ConferencePublication).filter_by(id=cid_pub).first()
        if not row:
            continue
        if p.get("doi"):
            row.doi = p["doi"]
        cname = (p.get("conference_name") or p.get("venue") or "").strip()
        if cname and (_is_generic_venue(row.conference_name or "") or not (row.conference_name or "").strip()):
            row.conference_name = cname
        if p.get("core_ranking"):
            row.core_ranking = p["core_ranking"]
        if p.get("is_a_star") is not None:
            row.is_a_star = bool(p["is_a_star"])
        pub = (p.get("publisher") or "").strip()
        if pub and not (row.publisher or "").strip():
            row.publisher = pub
        idx = p.get("proc_indexed_in")
        if isinstance(idx, list) and idx:
            row.indexed_in = ", ".join(str(x) for x in idx if x)
        elif isinstance(idx, str) and idx.strip() and not (row.indexed_in or "").strip():
            row.indexed_in = idx.strip()
        mat = p.get("maturity") or {}
        ord_ed = mat.get("ordinal_edition")
        if ord_ed and not (row.conference_series or "").strip():
            row.conference_series = f"{ord_ed} edition (parsed from venue/title)"
        role = _canonical_authorship_role(p.get("authorship_role_api"))
        if role:
            row.authorship_role = role


def _upsert_research_score(db: Session, candidate_id: int, result: ResearchAnalysisResult) -> None:
    """Write research score into CandidateAssessment (upsert pattern)."""
    existing = (
        db.query(CandidateAssessment)
        .filter_by(candidate_id=candidate_id)
        .order_by(CandidateAssessment.generated_at.desc())
        .first()
    )

    score_blob = json.dumps({
        "final_score":      result.final_score,
        "normalized_score": result.normalized_score,
        "base_score":       result.base_score,
        "grade":            result.grade,
        "components": {k: {"score": v.get("score"), "reasons": v.get("reasons", [])}
                       for k, v in result.components.items()},
        "bonus_breakdown":  result.bonus_breakdown,
        "counts":           result.counts,
        "warnings":         result.warnings,
        "recommendations":  result.recommendations,
        "enrichment_audit": result.enrichment_audit,
    })

    rs_10 = research_strength_for_persist(result.normalized_score)
    if existing:
        existing.research_strength_score = rs_10
        existing.assessment_version       = "m2_research_v2"
        # Store full detail in analysis_json on the candidate row (done in main fn)
    else:
        db.add(CandidateAssessment(
            candidate_id=candidate_id,
            assessment_version="m2_research_v2",
            research_strength_score=rs_10,
            overall_summary=(
                f"Research score: {result.grade} ({result.final_score:.1f}/110). "
                f"{len(result.warnings)} warning(s)."
            ),
        ))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def run_research_analysis(db: Session, candidate_id: int) -> ResearchAnalysisResult:
    """
    Entry point called by the router.
    Sync wrapper — runs async enrichment via a dedicated event loop (Celery-safe).
    """
    logger.info("[ResearchAnalysis] Starting for candidate_id=%d", candidate_id)

    # 1. Load candidate data from DB
    cand: Optional[Candidate] = db.query(Candidate).filter_by(id=candidate_id).first()
    if not cand:
        raise ValueError(f"Candidate {candidate_id} not found")

    candidate_name = cand.name

    # 2. Pull raw data
    j_rows: list[JournalPublication]    = db.query(JournalPublication).filter_by(candidate_id=candidate_id).all()
    c_rows: list[ConferencePublication] = db.query(ConferencePublication).filter_by(candidate_id=candidate_id).all()
    sup_rows: list[SupervisionRecord]   = db.query(SupervisionRecord).filter_by(candidate_id=candidate_id).all()
    book_rows: list[Book]               = db.query(Book).filter_by(candidate_id=candidate_id).all()
    patent_rows: list[Patent]           = db.query(Patent).filter_by(candidate_id=candidate_id).all()

    # 3. Serialize to plain dicts for enrichment
    j_pubs = [
        {"id": p.id, "pub_type": "journal", "title": p.title,
         "venue": p.journal_name, "issn": p.issn, "doi": p.doi,
         "year": p.year, "authors": p.authors,
         "authorship_role": p.authorship_role,
         "wos_indexed": p.wos_indexed, "scopus_indexed": p.scopus_indexed,
         "quartile": p.quartile, "impact_factor": p.impact_factor}
        for p in j_rows
    ]
    c_pubs = [
        {"id": p.id, "pub_type": "conference", "title": p.title,
         "conference_name": p.conference_name, "doi": p.doi,
         "year": p.year, "authors": p.authors,
         "authorship_role": p.authorship_role,
         "core_ranking": p.core_ranking, "publisher": p.publisher,
         "indexed_in": p.indexed_in, "is_a_star": p.is_a_star}
        for p in c_rows
    ]
    sup_list  = [{"student_level": s.student_level, "supervision_role": s.supervision_role}
                 for s in sup_rows]
    books_list   = [{"authorship_role": b.authorship_role, "title": b.title} for b in book_rows]
    patents_list = [{"patent_no": p.patent_no, "title": p.title, "status": p.status}
                    for p in patent_rows]

    # 4. Async enrichment (title recovery + API calls)
    enrichment_audit: dict = {"skipped": False, "warnings": [], "errors": []}
    if j_pubs or c_pubs:
        logger.info("[ResearchAnalysis] Enriching %d journals + %d conferences...",
                    len(j_pubs), len(c_pubs))
        try:
            j_pubs, c_pubs, enrich_audit = run_coro_sync(
                enrich_all_publications(j_pubs, c_pubs, candidate_name)
            )
            enrichment_audit.update(enrich_audit)
        except Exception as exc:
            logger.error("[ResearchAnalysis] Enrichment failed: %s — scoring with raw data", exc)
            enrichment_audit["warnings"].append(f"Enrichment runner crashed: {exc!s}")

    # 5. Apply local dataset lookups AFTER enrichment (ISSN/venue now recovered)
    scimago = ScimagoLookup.get()
    core    = CoreLookup.get()

    for p in j_pubs:
        issn = (p.get("issn") or "").strip()
        cv_q = (str(p.get("quartile") or "").strip().upper() or None)
        if issn:
            q_cat = scimago.lookup_quartile(issn)
            if q_cat:
                if cv_q and cv_q != str(q_cat).strip().upper():
                    enrichment_audit["warnings"].append(
                        f"Journal quartile for '{(p.get('title') or '')[:50]}' set from Scimago ISSN ({q_cat}); "
                        f"CV/extraction had {cv_q}."
                    )
                p["quartile"] = q_cat
                p["quartile_source"] = "scimago_issn"
            elif cv_q:
                p["quartile_source"] = "cv_unverified"
                enrichment_audit["warnings"].append(
                    f"ISSN not found in Scimago catalog — quartile {cv_q} for "
                    f"'{(p.get('title') or '')[:50]}' is not externally verified."
                )
        elif cv_q:
            p["quartile_source"] = "cv_unverified"
            enrichment_audit["warnings"].append(
                f"No ISSN recovered — quartile {cv_q} for '{(p.get('title') or '')[:50]}' is not externally verified."
            )
        p["is_legitimate"] = bool(p.get("quartile") or p.get("crossref_found") or p.get("oa_scopus_proxy"))

    for p in c_pubs:
        venue = p.get("conference_name") or ""
        title = p.get("title") or ""
        if not p.get("core_ranking") or str(p.get("core_ranking", "")).lower() in ("unranked", "none", ""):
            rank = core.lookup_rank(venue)
            if rank:
                p["core_ranking"] = rank
                p["is_a_star"] = rank.strip().upper() == "A*"
        indexing = detect_conference_indexing(
            venue,
            p.get("publisher_cr", ""),
            p.get("publisher", ""),
        )
        p.update({
            "publisher": p.get("publisher") or indexing["publisher"],
            "proc_indexed_in": indexing["proc_indexed_in"],
            "proc_scopus_indexed": indexing["proc_scopus_indexed"],
        })
        ordinal = _extract_ordinal(venue, title) or _extract_ordinal(p.get("venue") or "")
        maturity = _build_maturity(ordinal, p.get("earliest_conf_year"))
        p["maturity"] = maturity

    _persist_enriched_publications(db, j_pubs, c_pubs)

    # 6. Score
    pub_q  = _score_publication_quality(j_pubs, c_pubs)
    auth_s = _score_authorship(j_pubs, c_pubs)
    collab = _score_collaboration(j_pubs, c_pubs, candidate_name)
    conf_m = _score_conference_maturity(c_pubs)
    sup_s  = _score_supervision(sup_list)
    pb     = _score_patents_books(patents_list, books_list)  # reference only

    max_base   = 82
    base_total = min(
        pub_q["score"] + auth_s["score"] + collab["score"] + conf_m["score"] + sup_s["score"],
        max_base,
    )
    normalized = round((base_total / max_base) * 100.0, 1)

    has_books   = len(books_list) > 0
    has_patents = len(patents_list) > 0
    bonus_books   = 5.0 if has_books else 0.0
    bonus_patents = 5.0 if has_patents else 0.0
    total_bonuses = bonus_books + bonus_patents

    final_score = round(normalized + total_bonuses, 1)

    if   final_score >= 100: grade = "EXCEPTIONAL"
    elif final_score >= 90:  grade = "EXCELLENT"
    elif final_score >= 77:  grade = "GOOD"
    elif final_score >= 65:  grade = "SATISFACTORY"
    elif final_score >= 49:  grade = "DEVELOPING"
    else:                    grade = "WEAK"

    all_warnings: list[str] = []
    for comp in [pub_q, auth_s, collab, conf_m, sup_s]:
        all_warnings.extend(comp.get("warnings", []))
    all_warnings.extend(enrichment_audit.get("warnings", []))

    components = {
        "publication_quality":    pub_q,
        "authorship_strength":    auth_s,
        "research_collaboration": collab,
        "conference_maturity":    conf_m,
        "supervision_record":     sup_s,
        "patents_books":          pb,  # reference only, not in base
    }

    result = ResearchAnalysisResult(
        candidate_id=candidate_id,
        final_score=final_score,
        normalized_score=normalized,
        base_score=round(base_total, 1),
        grade=grade,
        components={k: {"score": v["score"], "max": v["max"],
                        "reasons": v.get("reasons", []),
                        "warnings": v.get("warnings", [])}
                    for k, v in components.items()},
        bonus_breakdown={
            "books":   {"present": has_books,   "bonus": bonus_books},
            "patents": {"present": has_patents,  "bonus": bonus_patents},
            "total":   total_bonuses,
        },
        counts={
            "total_journal_papers":    len(j_pubs),
            "total_conference_papers": len(c_pubs),
            "total_books":             len(books_list),
            "total_patents":           len(patents_list),
            "total_supervised":        len(sup_list),
        },
        warnings=all_warnings,
        recommendations=_build_recommendations(components, j_pubs, c_pubs),
        enrichment_audit=enrichment_audit,
    )

    # 7. Write to DB (upsert)
    try:
        _upsert_research_score(db, candidate_id, result)
        db.commit()
        logger.info(
            "[ResearchAnalysis] Done candidate=%d | %s | %.1f/110 (base=%.1f/82, norm=%.1f/100)",
            candidate_id, grade, final_score, base_total, normalized,
        )
    except Exception as exc:
        db.rollback()
        logger.error("[ResearchAnalysis] DB commit failed for candidate %d: %s", candidate_id, exc)
        raise

    return result
