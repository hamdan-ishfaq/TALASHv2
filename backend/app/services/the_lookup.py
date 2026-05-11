"""
the_lookup.py
-------------
Optional local Times Higher Education (THE) World University Rankings XLSX.

Place a workbook matching ``*THE*.xlsx`` in the project root (same pattern as QS).
Expected layout (mirrors common THE exports):
  Row 1: title row (skipped)
  Row 2: headers — col2 = overall rank, col3 = prior year rank (optional), col4 = institution, col5 = country/region

If no file is present, lookup returns None and callers leave ``institution_the_ranking`` unset.
"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import openpyxl

logger = logging.getLogger(__name__)


class _THEEntry:
    __slots__ = ("institution", "location", "rank", "rank_prior")

    def __init__(self, institution: str, location: str, rank: str | None, rank_prior: str | None):
        self.institution = institution.strip()
        self.location = (location or "").strip()
        self.rank = str(rank).strip() if rank else None
        self.rank_prior = str(rank_prior).strip() if rank_prior else None


class THERankingLookup:
    _instance: "THERankingLookup | None" = None
    _entries: list[_THEEntry]

    def __init__(self, xlsx_path: str | None):
        self._entries = []
        if not xlsx_path or not Path(xlsx_path).exists():
            logger.warning(
                "THE Rankings XLSX not found at %r — THE lookup disabled (transparent N/A in UI)",
                xlsx_path,
            )
            return
        self._load(xlsx_path)
        logger.info("THE Rankings loaded: %d institutions from %s", len(self._entries), xlsx_path)

    def _load(self, path: str) -> None:
        from app.services.ranking_xlsx import iter_ranking_rows

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        for institution, rank_p, rank_s, loc in iter_ranking_rows(ws):
            self._entries.append(
                _THEEntry(
                    institution=institution,
                    location=loc or "",
                    rank=rank_p or None,
                    rank_prior=rank_s or None,
                )
            )
        wb.close()

    @classmethod
    def get(cls) -> "THERankingLookup":
        if cls._instance is None:
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
                matches = sorted(root.glob("*THE*.xlsx"), key=lambda p: p.name.lower())
                if matches:
                    xlsx_path = str(matches[0])
                    break
            cls._instance = cls(xlsx_path)
        return cls._instance

    @staticmethod
    def _sim(a: str, b: str) -> float:
        return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()

    def lookup(self, institution_name: str | None) -> Optional[dict]:
        if not institution_name or not self._entries:
            return None
        query = institution_name.strip()
        best: Optional[_THEEntry] = None
        best_score = 0.0
        for e in self._entries:
            s = self._sim(query, e.institution)
            if s > best_score:
                best_score, best = s, e
        if best is None or best_score < 0.82:
            return None
        raw_rank = best.rank or ""
        rank_int: int | None = None
        try:
            m = re.match(r"^=?\s*(\d+)", str(raw_rank))
            if m:
                rank_int = int(m.group(1))
            elif "-" in str(raw_rank):
                rank_int = int(str(raw_rank).split("-")[0].strip().lstrip("="))
        except (ValueError, AttributeError):
            rank_int = None
        return {
            "rank": raw_rank,
            "rank_int": rank_int,
            "rank_prior": best.rank_prior,
            "country": best.location or None,
            "match_score": round(best_score, 3),
        }
