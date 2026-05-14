"""
research_enrichment.py
----------------------
Async API enrichment layer for research publications.

All external API calls live here — separated from scoring so they can be
tested and replaced independently.

External APIs used:
  - Crossref   (title search + DOI lookup) — free, no key required
  - OpenAlex   (journal stats + conference age) — free, no key required
  - wos-journal.info (WoS/impact-factor scrape) — free, fragile, has fallback

Called from research_analysis.py via asyncio.run().
"""
from __future__ import annotations

import asyncio
import logging
import re
from difflib import SequenceMatcher
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
CROSSREF_SCORE_THRESHOLD = 85   # Crossref relevance score gate
TITLE_SIM_THRESHOLD      = 0.82 # fuzzy similarity gate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


# ============================================================================
# STEP 0 — Title-based metadata recovery
# ============================================================================

def _best_crossref_item(items: list, query_title: str) -> tuple[Optional[dict], float]:
    """Pick best Crossref result by API score + title similarity."""
    if not items:
        return None, 0.0
    best_item, best_score = None, 0.0
    for item in items[:5]:
        api_score = item.get("score", 0)
        titles    = item.get("title", [])
        item_title = titles[0] if titles else ""
        sim = _sim(query_title, item_title)
        combined = api_score if sim >= 0.50 else 0.0
        if combined > best_score:
            best_score, best_item = combined, item
    return best_item, best_score


def _extract_issn(item: dict) -> Optional[str]:
    issn_l = item.get("ISSN-L")
    if issn_l:
        return issn_l if isinstance(issn_l, str) else issn_l[0]
    issns = item.get("ISSN", [])
    return issns[0] if issns else None


def _extract_venue(item: dict) -> Optional[str]:
    container = item.get("container-title", [])
    if container:
        return container[0]
    event = item.get("event", {})
    if isinstance(event, dict) and event.get("name"):
        return event["name"]
    return None


def _extract_year(item: dict) -> Optional[int]:
    for key in ("published", "published-print", "published-online"):
        dp = item.get(key, {})
        if isinstance(dp, dict):
            parts = dp.get("date-parts", [[]])
            if parts and parts[0]:
                return int(parts[0][0])
    return None


async def _resolve_via_crossref(session: aiohttp.ClientSession, title: str) -> dict:
    """Search Crossref by title. Returns recovered metadata dict or {}."""
    if not title:
        return {}
    try:
        params = {
            "query.title": title,
            "rows": 5,
            "select": (
                "DOI,title,ISSN,ISSN-L,container-title,publisher,"
                "score,published,published-print,published-online,event,type"
            ),
        }
        headers = {"User-Agent": "TALASH-ResearchProfiler/1.0 (research@talash.edu)"}
        async with session.get(
            "https://api.crossref.org/works",
            params=params, headers=headers,
            timeout=aiohttp.ClientTimeout(total=14),
        ) as r:
            if r.status != 200:
                return {}
            raw = await r.json(content_type=None)

        items = raw.get("message", {}).get("items", [])
        item, score = _best_crossref_item(items, title)
        if not item:
            return {}

        titles_list = item.get("title", [])
        item_title  = titles_list[0] if titles_list else ""
        sim = _sim(title, item_title)

        if score < CROSSREF_SCORE_THRESHOLD and sim < TITLE_SIM_THRESHOLD:
            logger.debug("[CR title] LOW CONFIDENCE score=%.1f sim=%.2f: %s", score, sim, title[:55])
            return {}

        result = {
            "doi":          item.get("DOI"),
            "issn":         _extract_issn(item),
            "venue":        _extract_venue(item),
            "year":         _extract_year(item),
            "publisher_cr": item.get("publisher", ""),
            "cr_type":      item.get("type", ""),
        }
        logger.debug("[CR title] ✓ score=%.1f sim=%.2f doi=%s issn=%s",
                     score, sim, result["doi"], result["issn"])
        return result
    except Exception as exc:
        logger.debug("[CR title error] %s", exc)
        return {}


async def _resolve_via_openalex(session: aiohttp.ClientSession, title: str) -> dict:
    """Fallback: search OpenAlex by title."""
    if not title:
        return {}
    try:
        params = {
            "search":   title,
            "per-page": 3,
            "select":   "doi,ids,primary_location,publication_year,title",
        }
        async with session.get(
            "https://api.openalex.org/works",
            params=params,
            timeout=aiohttp.ClientTimeout(total=12),
        ) as r:
            data = await r.json(content_type=None)

        results = data.get("results", [])
        if not results:
            return {}

        best, best_sim = None, 0.0
        for w in results:
            s = _sim(title, w.get("title") or "")
            if s > best_sim:
                best_sim, best = s, w

        if best_sim < TITLE_SIM_THRESHOLD:
            logger.debug("[OA title] LOW SIM %.2f: %s", best_sim, title[:55])
            return {}

        doi = (best.get("doi") or "").replace("https://doi.org/", "") or None
        year = best.get("publication_year")
        src  = (best.get("primary_location") or {}).get("source") or {}
        issn_list = src.get("issn") or []
        issn  = issn_list[0] if issn_list else (src.get("issn_l") or None)
        venue = src.get("display_name") or None

        logger.debug("[OA title] ✓ sim=%.2f doi=%s issn=%s", best_sim, doi, issn)
        return {"doi": doi, "issn": issn, "venue": venue, "year": year}
    except Exception as exc:
        logger.debug("[OA title error] %s", exc)
        return {}


_GENERIC_VENUES = {
    "international journal", "international conference",
    "journal", "conference", "proceedings", "unknown", "",
}


def _is_generic_venue(venue: str) -> bool:
    return (venue or "").strip().lower() in _GENERIC_VENUES


async def recover_metadata_by_title(pub: dict,
                                    session: aiohttp.ClientSession) -> dict:
    """
    Fill missing doi / issn / venue / year by searching title on Crossref
    (with OpenAlex fallback). Never overwrites existing real data.
    """
    title = (pub.get("title") or "").strip()
    if not title:
        return pub

    needs_doi   = not pub.get("doi")
    needs_issn  = not pub.get("issn")
    needs_venue = _is_generic_venue(pub.get("venue") or "")

    if not (needs_doi or needs_issn or needs_venue):
        return pub  # nothing missing

    logger.info("[Title recovery] '%s...' doi:%s issn:%s venue:%s",
                title[:55], needs_doi, needs_issn, needs_venue)

    # Crossref first
    meta = await _resolve_via_crossref(session, title)

    # OpenAlex fallback when both doi + issn still missing
    if not meta or (needs_issn and not meta.get("issn") and needs_doi and not meta.get("doi")):
        oa = await _resolve_via_openalex(session, title)
        for k, v in oa.items():
            if v and not meta.get(k):
                meta[k] = v

    # Apply — only fill gaps, never overwrite
    if meta.get("doi")   and needs_doi:
        pub["doi"]   = meta["doi"]
    if meta.get("issn")  and needs_issn:
        pub["issn"]  = meta["issn"]
    if meta.get("venue") and needs_venue:
        pub["venue"] = meta["venue"]
    if meta.get("year")  and not pub.get("year"):
        pub["year"]  = meta["year"]

    # Auto-correct pub_type from Crossref type
    cr_type = meta.get("cr_type", "")
    if cr_type == "proceedings-article" and pub.get("pub_type") != "conference":
        pub["pub_type"] = "conference"
        logger.info("    → pub_type corrected → conference")
    elif cr_type == "journal-article" and pub.get("pub_type") != "journal":
        pub["pub_type"] = "journal"
        logger.info("    → pub_type corrected → journal")

    if meta.get("publisher_cr"):
        pub["_publisher_hint"] = meta["publisher_cr"]

    return pub


# ============================================================================
# STEP 1 — Journal enrichment
# ============================================================================

async def fetch_openalex_journal(session: aiohttp.ClientSession,
                                  issn: str) -> dict:
    """Get citation stats and h-index from OpenAlex for a journal ISSN."""
    if not issn:
        return {}
    try:
        async with session.get(
            f"https://api.openalex.org/sources?filter=issn:{issn}",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            data = await r.json(content_type=None)
        results = data.get("results", [])
        if not results:
            return {}
        stats   = results[0].get("summary_stats", {})
        raw_2yr = stats.get("2yr_mean_citedness")
        return {
            "found":             True,
            "avg_citations_2yr": round(raw_2yr, 3) if raw_2yr is not None else None,
            "h_index":           stats.get("h_index"),
            "scopus_proxy":      (stats.get("h_index") or 0) > 10,
        }
    except Exception:
        return {}


async def fetch_wos_info(session: aiohttp.ClientSession, issn: str) -> dict:
    """
    Scrape wos-journal.info for WoS indexing + impact factor.
    Fragile — has fallback: returns wos_indexed=False on any error.
    """
    if not issn:
        return {"wos_indexed": False, "impact_factor": None}
    try:
        async with session.get(
            f"https://wos-journal.info/journalid/{issn}",
            timeout=aiohttp.ClientTimeout(total=12),
        ) as r:
            text = await r.text()

        if "Journal Citation Reports" not in text:
            return {"wos_indexed": False, "impact_factor": None}

        impact_factor = None
        patterns = [
            r"Impact\s+Factor[^\d]{0,30}?([\d]+[.,][\d]+)",
            r"JIF[^\d]{0,20}?([\d]+[.,][\d]+)",
            r"<td[^>]*>\s*([\d]+[.,][\d]+)\s*</td>(?=[^<]*Impact)",
            r"([\d]+[.,][\d]+)\s*(?:Impact Factor)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if m:
                try:
                    val = float(m.group(1).replace(",", "."))
                    if 0.05 <= val <= 100:
                        impact_factor = val
                        break
                except ValueError:
                    continue

        return {"wos_indexed": True, "impact_factor": impact_factor}

    except Exception as exc:
        logger.debug("[WoS scrape] fallback (error: %s)", exc)
        return {"wos_indexed": False, "impact_factor": None}


async def fetch_crossref_doi(session: aiohttp.ClientSession,
                              doi: str, candidate_name: str) -> dict:
    """Fetch authorship role and publisher via DOI lookup."""
    if not doi:
        return {"found": False}
    try:
        headers = {"User-Agent": "TALASH-ResearchProfiler/1.0 (research@talash.edu)"}
        async with session.get(
            f"https://api.crossref.org/works/{doi}",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=12),
        ) as r:
            if r.status != 200:
                return {"found": False}
            raw = await r.json(content_type=None)
        msg = raw.get("message") or {}
        return {
            "found":     True,
            "role":      _detect_authorship_role(msg.get("author") or [], candidate_name),
            "publisher": msg.get("publisher", ""),
        }
    except Exception:
        return {"found": False}


def _detect_authorship_role(authors: list, candidate_name: str) -> str:
    """Detect first/corresponding/co-author from CrossRef author list."""
    if not authors or not candidate_name:
        return "unknown"
    parts    = candidate_name.lower().split()
    last     = parts[-1]
    first    = parts[0] if len(parts) > 1 else ""
    is_first = is_corr = matched = False

    for i, a in enumerate(authors):
        family = a.get("family", "").lower()
        given  = a.get("given",  "").lower()
        if last not in family and last not in given:
            continue
        if first and first not in given and first not in family:
            continue
        matched = True
        if a.get("sequence") == "first" or i == 0:
            is_first = True
        for aff in a.get("affiliation", []):
            if "correspond" in str(aff).lower():
                is_corr = True
        break

    if not matched:           return "unknown"
    if is_first and is_corr:  return "first_and_corresponding"
    if is_first:              return "first_author"
    if is_corr:               return "corresponding_author"
    return "co_author"


# ============================================================================
# STEP 1 — Conference enrichment
# ============================================================================

# Publisher keyword rules → (keywords, label, databases)
PUBLISHER_RULES = [
    (["IEEE"],                                                  "IEEE",      ["IEEE Xplore", "Scopus"]),
    (["ACM ", " ACM", "(ACM)", "SIGCOMM", "SIGGRAPH",
      "SIGKDD", "CHI "],                                       "ACM",       ["ACM Digital Library", "Scopus"]),
    (["SPRINGER", "LECTURE NOTES", "LNCS", "LNAI", "LNEE"],   "Springer",  ["Springer", "Scopus"]),
    (["ELSEVIER", "PROCEDIA"],                                 "Elsevier",  ["Elsevier", "Scopus"]),
    (["WILEY"],                                                "Wiley",     ["Wiley", "Scopus"]),
    (["USENIX"],                                               "USENIX",    ["USENIX"]),
    (["IFIP"],                                                 "IFIP",      ["Springer", "Scopus"]),
    (["AAAI"],                                                 "AAAI",      ["AAAI", "Scopus"]),
    (["ICLR", "NEURIPS", "NIPS", "ICML"],                      "ML Conf",   ["OpenReview/PMLR", "Scopus"]),
    (["INTERSPEECH", "ICASSP", "EUSIPCO"],                     "ISCA/IEEE", ["IEEE Xplore", "Scopus"]),
]

SCOPUS_SIGNALS = [
    "INTERNATIONAL CONFERENCE", "ANNUAL CONFERENCE", "SYMPOSIUM ON",
    "WORKSHOP ON", "WORLD CONGRESS", "GLOBAL CONFERENCE",
]


def detect_conference_indexing(venue: str,
                                crossref_pub: str = "",
                                publisher_hint: str = "") -> dict:
    combined = f"{venue} {crossref_pub} {publisher_hint}".upper()
    for keywords, label, databases in PUBLISHER_RULES:
        if any(kw in combined for kw in keywords):
            return {
                "publisher":           label,
                "proc_indexed_in":     databases,
                "proc_scopus_indexed": "Scopus" in databases,
            }
    possibly_scopus = any(sig in combined for sig in SCOPUS_SIGNALS)
    databases = ["Scopus (possible)"] if possibly_scopus else []
    return {
        "publisher":           "Unknown",
        "proc_indexed_in":     databases,
        "proc_scopus_indexed": possibly_scopus,
    }


async def fetch_openalex_conf_age(session: aiohttp.ClientSession,
                                   venue: str) -> dict:
    """Estimate conference age via earliest paper year in OpenAlex."""
    if not venue:
        return {}
    strategies: list[str] = []
    m = re.search(r"\(([A-Z0-9\-]+)\)", venue)
    if m:
        strategies.append(m.group(1))
    clean = re.sub(r"^\d{4}\s+", "", venue)
    clean = re.sub(r"\([^)]*\)", "", clean).strip()
    words = [w for w in clean.split() if len(w) > 3][:5]
    if words:
        strategies.append(" ".join(words))
    strategies.append(" ".join(venue.split()[:3]))

    for q in strategies:
        try:
            url = (
                "https://api.openalex.org/works"
                f"?filter=primary_location.source.display_name.search:{q}"
                "&sort=publication_year:asc&per-page=1"
            )
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), ssl=True) as r:
                data = await r.json(content_type=None)
            results = data.get("results", [])
            if results:
                yr = results[0].get("publication_year")
                if yr and int(yr) > 1950:
                    return {"earliest_year": int(yr)}
        except Exception:
            continue
    return {}


# ============================================================================
# Per-publication enrichment orchestrator
# ============================================================================

async def enrich_journal_pub(pub: dict, session: aiohttp.ClientSession,
                              candidate_name: str) -> dict:
    """Full enrichment for one journal publication."""
    pub = await recover_metadata_by_title(pub, session)

    issn = pub.get("issn") or ""
    doi  = pub.get("doi") or ""

    wos, oa, cr = await asyncio.gather(
        fetch_wos_info(session, issn),
        fetch_openalex_journal(session, issn),
        fetch_crossref_doi(session, doi, candidate_name),
    )

    # impact_factor: WoS value preferred; fall back to OA 2yr mean citedness
    impact_factor = wos.get("impact_factor") if wos.get("impact_factor") is not None else oa.get("avg_citations_2yr")

    pub.update({
        "wos_indexed":       wos.get("wos_indexed", False),
        "impact_factor":     impact_factor,
        "avg_citations_2yr": oa.get("avg_citations_2yr"),
        "h_index":           oa.get("h_index"),
        "oa_scopus_proxy":   oa.get("scopus_proxy", False),
        "crossref_found":    cr.get("found", False),
        "authorship_role_api": cr.get("role", "unknown"),
        "publisher_cr":      cr.get("publisher", ""),
    })
    return pub


async def enrich_conference_pub(pub: dict, session: aiohttp.ClientSession,
                                 candidate_name: str) -> dict:
    """Full enrichment for one conference publication."""
    pub = await recover_metadata_by_title(pub, session)

    doi   = pub.get("doi") or ""
    venue = pub.get("venue") or pub.get("conference_name") or ""

    cr, age_data = await asyncio.gather(
        fetch_crossref_doi(session, doi, candidate_name),
        fetch_openalex_conf_age(session, venue),
    )

    pub.update({
        "crossref_found":      cr.get("found", False),
        "authorship_role_api": cr.get("role", "unknown"),
        "publisher_cr":        cr.get("publisher", ""),
        "earliest_conf_year":  age_data.get("earliest_year"),
    })
    return pub


async def enrich_all_publications(
    journals: list[dict],
    conferences: list[dict],
    candidate_name: str,
    max_concurrent: int = 10,
) -> tuple[list[dict], list[dict]]:
    """
    Run all enrichment tasks concurrently.
    Returns (enriched_journals, enriched_conferences).
    """
    connector = aiohttp.TCPConnector(limit=max_concurrent, ssl=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        journal_tasks = [
            enrich_journal_pub(dict(p), session, candidate_name)
            for p in journals
        ]
        conf_tasks = [
            enrich_conference_pub(dict(p), session, candidate_name)
            for p in conferences
        ]
        results = await asyncio.gather(*(journal_tasks + conf_tasks))

    n = len(journals)
    return list(results[:n]), list(results[n:])
