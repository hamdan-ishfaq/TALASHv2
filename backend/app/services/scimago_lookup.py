"""
scimago_lookup.py
-----------------
Singleton loader for the Scimago JR 2025 CSV.
Maps ISSN → SJR Best Quartile (Q1/Q2/Q3/Q4).

Dataset path inside Docker container: /app/scimagojr_2025.csv
(mounted from ./scimagojr 2025.csv on host via docker-compose volume)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Candidate search paths (tried in order, first match wins)
# ---------------------------------------------------------------------------
_SEARCH_PATHS = [
    Path("/app/scimagojr_2025.csv"),                 # Docker mount
    Path("/app/scimagojr 2025.csv"),                 # fallback with space
    Path(__file__).resolve().parents[3] / "scimagojr_2025.csv",
    Path(__file__).resolve().parents[3] / "scimagojr 2025.csv",
]


def _normalize_issn(issn: str) -> str:
    """Strip dashes/spaces/quotes and lowercase."""
    return re.sub(r'[-\s"]', "", str(issn)).lower()


class ScimagoLookup:
    """
    Singleton — call ``ScimagoLookup.get()`` to obtain the shared instance.
    Thread-safe for read-only access (built once at startup).
    """
    _instance: "ScimagoLookup | None" = None
    _issn_map: dict[str, str]   # normalized_issn → quartile string

    def __init__(self, csv_path: str) -> None:
        self._issn_map = {}
        self._load(csv_path)
        logger.info("Scimago loaded: %d ISSNs from %s", len(self._issn_map), csv_path)

    def _load(self, path: str) -> None:
        try:
            df = pd.read_csv(path, sep=";", encoding="utf-8", on_bad_lines="skip")
            df["Issn"] = df["Issn"].astype(str).str.replace('"', "").str.strip()
            for _, row in df.iterrows():
                q = row.get("SJR Best Quartile")
                if pd.isna(q):
                    continue
                for raw in str(row["Issn"]).split(","):
                    norm = _normalize_issn(raw)
                    if norm:
                        self._issn_map[norm] = str(q).strip()
        except Exception as exc:
            logger.error("Failed to load Scimago CSV from %s: %s", path, exc)

    @classmethod
    def get(cls) -> "ScimagoLookup":
        if cls._instance is None:
            csv_path: str | None = None
            for p in _SEARCH_PATHS:
                if p.exists():
                    csv_path = str(p)
                    break
            if csv_path is None:
                logger.warning(
                    "Scimago CSV not found in any search path — quartile lookup disabled. "
                    "Expected at /app/scimagojr_2025.csv inside the container."
                )
                cls._instance = cls.__new__(cls)
                cls._instance._issn_map = {}
                return cls._instance
            cls._instance = cls(csv_path)
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def lookup_quartile(self, issn: str) -> Optional[str]:
        """Return 'Q1'/'Q2'/'Q3'/'Q4' or None."""
        if not issn:
            return None
        norm = _normalize_issn(issn)
        return self._issn_map.get(norm)

    def __len__(self) -> int:
        return len(self._issn_map)
