"""
topic_analysis.py
-----------------
§3.6 Topic variability: cluster distribution, entropy-based diversity, dominant theme.
Uses TopicCluster rows when present; otherwise buckets titles/keywords heuristically.
Adds per-year dominant theme trend (§3.6 temporal focus).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.models import Candidate, ConferencePublication, JournalPublication, TopicCluster

logger = logging.getLogger(__name__)

# Coarse CS / IT buckets for heuristic tagging when LLM topic_category is missing
_BUCKET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Machine Learning / AI": ("machine learning", "deep learning", "neural", "llm", "transformer", "classification", "reinforcement"),
    "Computer Vision": ("vision", "image", "segmentation", "detection", "cnn", "object detection"),
    "NLP / Text": ("nlp", "natural language", "text", "sentiment", "token", "language model"),
    "Security": ("security", "crypt", "malware", "privacy", "authentication"),
    "Networks / IoT": ("network", "routing", "wireless", "iot", "5g", "sdn"),
    "Software Engineering": ("software", "testing", "maintenance", "agile", "repository"),
    "Data / DB / Big Data": ("database", "sql", "big data", "spark", "analytics", "data mining"),
    "HCI / Graphics": ("hci", "interface", "visualization", "graphics", "vr", "ar"),
    "Theory / Algorithms": ("algorithm", "complexity", "graph theory", "optimization"),
}


def _bucket_for_text(text: str) -> str:
    t = (text or "").lower()
    for bucket, kws in _BUCKET_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return bucket
    return "Other / General"


def _shannon_entropy(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        if c <= 0:
            continue
        p = c / total
        h -= p * math.log(p + 1e-12)
    return h


def _normalize_entropy(h: float, n_bins: int) -> float:
    """0 = single topic, 1 = uniform across n_bins (if n_bins>1)."""
    if n_bins <= 1:
        return 0.0
    h_max = math.log(n_bins)
    if h_max <= 0:
        return 0.0
    return max(0.0, min(1.0, h / h_max))


def _yearly_theme_rows(db: Session, candidate_id: int) -> tuple[list[dict[str, object]], str]:
    """Build {year, dominant_theme, publication_count, theme_shares} and a short stability note."""
    by_year: dict[int, dict[str, int]] = {}
    for j in db.query(JournalPublication).filter_by(candidate_id=candidate_id).all():
        y = j.year if j.year else None
        blob = " ".join(filter(None, [j.title, j.journal_name, j.topic_category or ""]))
        b = _bucket_for_text(blob)
        by_year.setdefault(y, {})
        by_year[y][b] = by_year[y].get(b, 0) + 1
    for c in db.query(ConferencePublication).filter_by(candidate_id=candidate_id).all():
        y = c.year if c.year else None
        blob = " ".join(filter(None, [c.title, c.conference_name, c.topic_category or ""]))
        b = _bucket_for_text(blob)
        by_year.setdefault(y, {})
        by_year[y][b] = by_year[y].get(b, 0) + 1

    rows: list[dict[str, object]] = []
    dominants: list[str] = []
    for y in sorted(by_year.keys(), key=lambda z: (z is None, z or 0)):
        counts = by_year[y]
        total = sum(counts.values())
        dom = max(counts, key=counts.get) if counts else "Other / General"
        dominants.append(dom)
        shares = {k: round(v / total, 3) for k, v in counts.items()} if total else {}
        rows.append(
            {
                "year": y,
                "year_label": "Undated" if y is None else str(y),
                "dominant_theme": dom,
                "publication_count": total,
                "theme_shares": shares,
            }
        )

    note = "Insufficient yearly data for trend."
    if len(dominants) >= 2:
        unique_dom = set(dominants)
        if len(unique_dom) == 1:
            note = "Research theme stable across observed publication years."
        elif len(unique_dom) <= 3:
            note = "Moderate thematic evolution across years (related clusters)."
        else:
            note = "Substantial thematic breadth or shift across publication years."

    return rows, note


@dataclass
class TopicAnalysisResult:
    candidate_id: int
    theme_counts: dict[str, int] = field(default_factory=dict)
    dominant_theme: str | None = None
    dominant_share: float = 0.0
    entropy: float = 0.0
    diversity_score: float = 0.0  # normalized entropy 0..1
    publication_count: int = 0
    source: str = "topic_clusters"
    topic_trend_by_year: list[dict[str, object]] = field(default_factory=list)
    topic_stability_note: str = ""

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "theme_counts": self.theme_counts,
            "dominant_theme": self.dominant_theme,
            "dominant_share_pct": round(self.dominant_share * 100, 1),
            "entropy": round(self.entropy, 4),
            "diversity_score": round(self.diversity_score, 4),
            "publication_count": self.publication_count,
            "source": self.source,
            "topic_trend_by_year": self.topic_trend_by_year,
            "topic_stability_note": self.topic_stability_note,
        }


def run_topic_analysis(db: Session, candidate_id: int) -> TopicAnalysisResult:
    cand = db.query(Candidate).filter_by(id=candidate_id).first()
    if not cand:
        raise ValueError(f"Candidate {candidate_id} not found")

    trend_rows, stability_note = _yearly_theme_rows(db, candidate_id)

    clusters = db.query(TopicCluster).filter_by(candidate_id=candidate_id).all()
    counts: dict[str, int] = {}

    if clusters:
        for row in clusters:
            name = (row.cluster_name or "Unknown").strip() or "Unknown"
            counts[name] = counts.get(name, 0) + 1
        source = "topic_clusters"
    else:
        pubs: list[str] = []
        for j in db.query(JournalPublication).filter_by(candidate_id=candidate_id).all():
            pubs.append(" ".join(filter(None, [j.title, j.journal_name, j.topic_category or ""])))
        for c in db.query(ConferencePublication).filter_by(candidate_id=candidate_id).all():
            pubs.append(" ".join(filter(None, [c.title, c.conference_name, c.topic_category or ""])))
        for blob in pubs:
            b = _bucket_for_text(blob)
            counts[b] = counts.get(b, 0) + 1
        source = "heuristic_title_buckets"

    total = sum(counts.values())
    if total == 0:
        out = TopicAnalysisResult(
            candidate_id=candidate_id,
            publication_count=0,
            source=source,
            topic_trend_by_year=trend_rows,
            topic_stability_note=stability_note,
        )
        logger.info("[TopicAnalysis] candidate=%d | no publications", candidate_id)
        return out

    dominant = max(counts, key=counts.get)
    h = _shannon_entropy(counts)
    div = _normalize_entropy(h, len(counts))

    out = TopicAnalysisResult(
        candidate_id=candidate_id,
        theme_counts=counts,
        dominant_theme=dominant,
        dominant_share=counts[dominant] / total,
        entropy=h,
        diversity_score=div,
        publication_count=total,
        source=source,
        topic_trend_by_year=trend_rows,
        topic_stability_note=stability_note,
    )
    logger.info(
        "[TopicAnalysis] candidate=%d | pubs=%d | dominant=%s | diversity=%.3f",
        candidate_id,
        total,
        dominant,
        div,
    )
    return out
