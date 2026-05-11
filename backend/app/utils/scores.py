"""Shared score scaling helpers (education/experience/skills are 0–10; research was historically 0–100)."""

from __future__ import annotations


def research_strength_on_ten(stored: float | None) -> float | None:
    """
    Return research strength on a 0–10 scale for UI and overall_rank blending.

    New pipeline stores 0–10. Legacy rows may store OpenAlex-style 0–100 normalized scores.
    """
    if stored is None:
        return None
    try:
        s = float(stored)
    except (TypeError, ValueError):
        return None
    if s > 10.5:
        return round(min(10.0, s / 10.0), 2)
    return round(min(10.0, s), 2)


def research_strength_for_persist(normalized_0_100: float) -> float:
    """Persist research on the same 0–10 scale as other CandidateAssessment slots."""
    try:
        x = float(normalized_0_100)
    except (TypeError, ValueError):
        return 0.0
    return round(min(10.0, max(0.0, x / 10.0)), 2)
