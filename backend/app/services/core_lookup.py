"""
core_lookup.py
--------------
Singleton loader for the CORE 2023 Conference Rankings CSV.
Maps conference name / acronym → CORE rank (A*, A, B, C).

Dataset path inside Docker container: /app/CORE.csv
(mounted from ./CORE.csv on host via docker-compose volume)
"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

_SEARCH_PATHS = [
    Path("/app/CORE.csv"),
    Path(__file__).resolve().parents[3] / "CORE.csv",
]

_COL_NAMES = ["ID", "Conference", "Acronym", "Source", "Rank",
              "Open_Access", "Paper_Count", "C8", "C9"]


class CoreLookup:
    """
    Singleton — call ``CoreLookup.get()`` to obtain the shared instance.
    """
    _instance: "CoreLookup | None" = None
    _df: pd.DataFrame

    def __init__(self, csv_path: str) -> None:
        self._df = pd.DataFrame(columns=["Conference", "Acronym", "Rank"])
        self._load(csv_path)
        logger.info("CORE rankings loaded: %d conferences from %s", len(self._df), csv_path)

    def _load(self, path: str) -> None:
        try:
            df = pd.read_csv(path, header=None, dtype=str, on_bad_lines="skip")
            df.columns = _COL_NAMES[: len(df.columns)]
            for col in ("Conference", "Acronym", "Rank"):
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()
            self._df = df
        except Exception as exc:
            logger.error("Failed to load CORE CSV from %s: %s", path, exc)

    @classmethod
    def get(cls) -> "CoreLookup":
        if cls._instance is None:
            csv_path: str | None = None
            for p in _SEARCH_PATHS:
                if p.exists():
                    csv_path = str(p)
                    break
            if csv_path is None:
                logger.warning(
                    "CORE CSV not found — conference ranking disabled. "
                    "Expected at /app/CORE.csv inside the container."
                )
                cls._instance = cls.__new__(cls)
                cls._instance._df = pd.DataFrame(columns=["Conference", "Acronym", "Rank"])
                return cls._instance
            cls._instance = cls(csv_path)
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def lookup_rank(self, venue: str, threshold: float = 0.72) -> Optional[str]:
        """
        Fuzzy-match venue against CORE list.
        Returns rank string ('A*', 'A', 'B', 'C') or None.
        """
        if not venue or self._df.empty:
            return None

        # 1. Try acronym in parentheses: "ICSE (ICSE)" → "ICSE"
        m = re.search(r"\(([A-Z0-9\-]+)\)", venue)
        if m:
            acronym = m.group(1).upper()
            res = self._df[self._df["Acronym"].str.upper() == acronym]
            if not res.empty:
                return res.iloc[0]["Rank"]

        # 2. Exact acronym match
        res = self._df[self._df["Acronym"].str.upper() == venue.strip().upper()]
        if not res.empty:
            return res.iloc[0]["Rank"]

        # 3. Strip leading year ("2024 ICSE" → "ICSE")
        clean = re.sub(r"^\d{4}\s+", "", venue).strip()

        # 4. Substring conference name match
        res = self._df[
            self._df["Conference"].str.contains(re.escape(clean), case=False, na=False)
        ]
        if not res.empty:
            return res.iloc[0]["Rank"]

        # 5. Fuzzy match
        best_score, best_rank = 0.0, None
        for _, row in self._df.iterrows():
            s = SequenceMatcher(None, clean.lower(), str(row["Conference"]).lower()).ratio()
            if s > best_score:
                best_score, best_rank = s, row["Rank"]
        return best_rank if best_score >= threshold else None
