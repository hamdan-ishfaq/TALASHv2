"""
qs_lookup.py
------------
Loads the '2026 QS World University Rankings' XLSX once at startup into memory.
Provides fuzzy institution name lookup returning (rank_2026, rank_2025, country).

QS workbook structure (confirmed from header inspection):
  Row 1 : Title/comment row  — skip
  Row 2 : Column headers
           col1=None  col2=2026  col3=2025  col4=Institution  col5=Location  ...
  Row 3+: Data
"""
from __future__ import annotations

import glob
import logging
import os
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import openpyxl

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal data structure
# ---------------------------------------------------------------------------
class _QSEntry:
    __slots__ = ("institution", "location", "rank_2026", "rank_2025")

    def __init__(self, institution: str, location: str, rank_2026: str | None, rank_2025: str | None):
        self.institution = institution.strip()
        self.location    = (location or "").strip()
        self.rank_2026   = str(rank_2026).strip() if rank_2026 else None
        self.rank_2025   = str(rank_2025).strip() if rank_2025 else None


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
class QSRankingLookup:
    """
    Singleton-style loader. Call ``QSRankingLookup.get()`` to obtain the
    shared instance.  Loads the XLSX from the project root on first access.
    """
    _instance: "QSRankingLookup | None" = None
    _entries: list[_QSEntry]

    def __init__(self, xlsx_path: str | None):
        self._entries = []
        if not xlsx_path or not Path(xlsx_path).exists():
            logger.warning(
                "QS Rankings XLSX not found at %r — institution QS lookup disabled",
                xlsx_path,
            )
            return
        self._load(xlsx_path)
        logger.info("QS Rankings loaded: %d institutions from %s", len(self._entries), xlsx_path)

    def _load(self, path: str) -> None:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active

        # Skip row 1 (title), row 2 (headers per spec), start reading from row 3
        # Column mapping: 1=seq, 2=rank2026, 3=rank2025, 4=Institution, 5=Location
        for row in ws.iter_rows(min_row=3, values_only=True):
            if not row or row[3] is None:   # col4 = Institution (0-indexed → col[3])
                continue
            institution = str(row[3]).strip()
            if not institution:
                continue
            self._entries.append(_QSEntry(
                institution=institution,
                location=str(row[4]) if row[4] else "",
                rank_2026=row[1],   # col2
                rank_2025=row[2],   # col3
            ))
        wb.close()

    @classmethod
    def get(cls) -> "QSRankingLookup":
        if cls._instance is None:
            # Search project root for the QS file
            search_roots = [
                Path("/home/mhamd/talashv3"),
                Path.cwd(),
                Path("/app"),
            ]
            try:
                search_roots.append(Path(__file__).resolve().parents[4])
            except IndexError:
                pass
            
            xlsx_path: str | None = None
            for root in search_roots:
                matches = list(root.glob("*QS*.xlsx"))
                if matches:
                    xlsx_path = str(matches[0])
                    break
            cls._instance = cls(xlsx_path)
        return cls._instance

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    def lookup(
        self,
        institution_name: str,
        threshold: float = 0.72,
    ) -> Optional[dict]:
        """
        Fuzzy-match institution_name against the QS list.
        Returns dict with keys: institution, rank_2026, rank_2025, country, match_score
        or None if no match above threshold.
        """
        if not institution_name or not institution_name.strip():
            return None

        query = institution_name.strip().lower()

        best_score = 0.0
        best_entry: _QSEntry | None = None

        for entry in self._entries:
            candidate = entry.institution.lower()
            # Try full match first
            score = SequenceMatcher(None, query, candidate).ratio()
            # Also try if query is a substring (catches "NUST" matching "National University of Sciences and Technology")
            if query in candidate or candidate in query:
                score = max(score, 0.80)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry is None or best_score < threshold:
            return None

        return {
            "institution":  best_entry.institution,
            "rank_2026":    best_entry.rank_2026,
            "rank_2025":    best_entry.rank_2025,
            "country":      best_entry.location,
            "match_score":  round(best_score, 3),
        }

    def lookup_rank_int(self, institution_name: str) -> Optional[int]:
        """
        Convenience: returns 2026 rank as int, or None.
        Handles ranks like '1', '=50', '501-510', '1001+' → returns lower bound.
        """
        result = self.lookup(institution_name)
        if not result or not result.get("rank_2026"):
            return None
        raw = str(result["rank_2026"]).strip().lstrip("=")
        # Handle ranges like "501-510"
        raw = raw.split("-")[0].replace("+", "")
        try:
            return int(raw)
        except ValueError:
            return None
