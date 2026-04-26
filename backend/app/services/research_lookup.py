"""
research_lookup.py
------------------
Singleton loaders for CORE (Conferences) and ScimagoJR (Journals) CSVs.
Authoritative source for Research Quality assessment (Module 2).
"""
import csv
import logging
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ===========================================================================
# SCIMAGO JR (JOURNALS)
# ===========================================================================
class _ScimagoEntry:
    __slots__ = ("title", "quartile", "h_index", "issn")
    def __init__(self, title: str, quartile: str, h_index: int, issn: str):
        self.title = title.strip()
        self.quartile = quartile.strip() if quartile else "Unknown"
        self.h_index = h_index
        self.issn = issn.strip()

class ScimagoLookup:
    _instance: "ScimagoLookup | None" = None

    def __init__(self, csv_path: str):
        self._entries: list[_ScimagoEntry] = []
        self._load(csv_path)
        logger.info("Scimago loaded: %d journals from %s", len(self._entries), csv_path)

    def _load(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    if row.get("Type", "").strip().lower() != "journal":
                        continue
                    
                    title = row.get("Title", "")
                    if not title:
                        continue
                        
                    quartile = row.get("SJR Best Quartile", "Unknown")
                    h_index_str = row.get("H index", "0")
                    issn = row.get("Issn", "")
                    
                    try:
                        h_index = int(h_index_str)
                    except ValueError:
                        h_index = 0
                        
                    self._entries.append(_ScimagoEntry(title, quartile, h_index, issn))
        except Exception as e:
            logger.error("Failed to load Scimago CSV: %s", e)

    @classmethod
    def get(cls) -> "ScimagoLookup":
        if cls._instance is None:
            # Search project root
            search_roots = [Path("/home/mhamd/talashv3"), Path.cwd(), Path("/app")]
            try: search_roots.append(Path(__file__).resolve().parents[4])
            except IndexError: pass
            
            csv_path: str | None = None
            for root in search_roots:
                matches = list(root.glob("*scimagojr*.csv"))
                if matches:
                    csv_path = str(matches[0])
                    break
            
            if csv_path is None:
                logger.warning("Scimago CSV not found! Journal lookups will fail.")
                cls._instance = cls.__new__(cls) # Dummy instance
                cls._instance._entries = []
            else:
                cls._instance = cls(csv_path)
        return cls._instance

    def lookup(self, title: str, threshold: float = 0.85) -> Optional[dict]:
        if not title or not title.strip() or not self._entries:
            return None
            
        query = title.strip().lower()
        best_score = 0.0
        best_entry: _ScimagoEntry | None = None

        for entry in self._entries:
            candidate = entry.title.lower()
            score = SequenceMatcher(None, query, candidate).ratio()
            # If substring match is perfect, give it a high score
            if score < 1.0 and (query in candidate or candidate in query):
                score = max(score, 0.90)
                
            if score > best_score:
                best_score = score
                best_entry = entry
                if score > 0.98: # Early exit for exact matches
                    break

        if best_entry is None or best_score < threshold:
            return None

        return {
            "title": best_entry.title,
            "quartile": best_entry.quartile,
            "h_index": best_entry.h_index,
            "match_score": best_score
        }

# ===========================================================================
# CORE (CONFERENCES)
# ===========================================================================
class _CoreEntry:
    __slots__ = ("title", "acronym", "rank")
    def __init__(self, title: str, acronym: str, rank: str):
        self.title = title.strip()
        self.acronym = acronym.strip()
        self.rank = rank.strip() if rank else "Unranked"

class CoreLookup:
    _instance: "CoreLookup | None" = None

    def __init__(self, csv_path: str):
        self._entries: list[_CoreEntry] = []
        self._load(csv_path)
        logger.info("CORE loaded: %d conferences from %s", len(self._entries), csv_path)

    def _load(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                # CORE CSV typically has no headers, format: ID, Title, Acronym, Source, Rank, ...
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 5:
                        title = row[1]
                        acronym = row[2]
                        rank = row[4]
                        self._entries.append(_CoreEntry(title, acronym, rank))
        except Exception as e:
            logger.error("Failed to load CORE CSV: %s", e)

    @classmethod
    def get(cls) -> "CoreLookup":
        if cls._instance is None:
            # Search project root
            search_roots = [Path("/home/mhamd/talashv3"), Path.cwd(), Path("/app")]
            try: search_roots.append(Path(__file__).resolve().parents[4])
            except IndexError: pass
            
            csv_path: str | None = None
            for root in search_roots:
                matches = list(root.glob("*CORE*.csv"))
                if matches:
                    csv_path = str(matches[0])
                    break
            
            if csv_path is None:
                logger.warning("CORE CSV not found! Conference lookups will fail.")
                cls._instance = cls.__new__(cls)
                cls._instance._entries = []
            else:
                cls._instance = cls(csv_path)
        return cls._instance

    def lookup(self, title: str, acronym: str = None, threshold: float = 0.85) -> Optional[dict]:
        if not title or not title.strip() or not self._entries:
            return None
            
        query = title.strip().lower()
        query_acronym = acronym.strip().lower() if acronym else None
        
        best_score = 0.0
        best_entry: _CoreEntry | None = None

        for entry in self._entries:
            candidate_title = entry.title.lower()
            candidate_acronym = entry.acronym.lower()
            
            # Boost score if acronym matches perfectly
            acronym_bonus = 0.0
            if query_acronym and candidate_acronym and query_acronym == candidate_acronym:
                acronym_bonus = 0.15
                
            score = SequenceMatcher(None, query, candidate_title).ratio() + acronym_bonus
            
            if score < 1.0 and (query in candidate_title or candidate_title in query):
                score = max(score, 0.90 + acronym_bonus)
                
            if score > best_score:
                best_score = score
                best_entry = entry
                if score >= 1.0:
                    break

        if best_entry is None or best_score < threshold:
            return None

        return {
            "title": best_entry.title,
            "acronym": best_entry.acronym,
            "rank": best_entry.rank,
            "match_score": min(best_score, 1.0)
        }
