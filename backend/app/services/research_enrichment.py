"""
research_enrichment.py
----------------------
Async API enrichment layer for research publications.

All external API calls live here — separated from scoring so they can be
tested and replaced independently.

External APIs used:
  - Crossref   (https://api.crossref.org) — free, no key; DOI + title search
  - OpenAlex   (https://api.openalex.org) — free, no key; journal ``/sources/issn:…`` + works search
  - DOAJ       (https://doaj.org/api/search/journals/…) — free OA journal registry by ISSN
  - wos-journal.info — optional HTML scrape (fragile); off by default (``TALASH_ENABLE_WOS_SCRAPE``)

Performance / etiquette:
  - In-process ISSN cache for OpenAlex + DOAJ (reduces duplicate HTTP across many papers).
  - Set ``TALASH_OPENALEX_MAILTO`` to your email for OpenAlex polite-pool rate limits.
  - ``TALASH_ENABLE_WOS_SCRAPE=1`` re-enables WoS scrape when you accept slower, brittle calls.

Called from research_analysis.py via sync_async.run_coro_sync().
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Any, Optional
from urllib.parse import quote

import aiohttp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared HTTP cache (per worker process; safe under asyncio single-thread)
# ---------------------------------------------------------------------------
_OA_ISSN_CACHE: dict[str, dict[str, Any]] = {}
_DOAJ_ISSN_CACHE: dict[str, dict[str, Any]] = {}
_EXT_CACHE_LOCK: asyncio.Lock | None = None
_EXT_CACHE_MAX = 8000


def _ext_lock() -> asyncio.Lock:
    global _EXT_CACHE_LOCK
    if _EXT_CACHE_LOCK is None:
        _EXT_CACHE_LOCK = asyncio.Lock()
    return _EXT_CACHE_LOCK


def _trim_cache(store: dict[str, Any]) -> None:
    if len(store) <= _EXT_CACHE_MAX:
        return
    for i, k in enumerate(list(store.keys())):
        if i >= _EXT_CACHE_MAX // 2:
            break
        store.pop(k, None)


def _openalex_append_mailto(url: str) -> str:
    mailto = os.getenv("TALASH_OPENALEX_MAILTO", "").strip()
    if not mailto:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}mailto={quote(mailto)}"


def _normalize_issn_key(issn: str) -> str:
    return re.sub(r"[-\s]", "", (issn or "")).lower()


def _issn_display(issn: str) -> str:
    """Prefer hyphenated ISSN for OpenAlex ``sources/issn:`` URLs."""
    raw = re.sub(r"[^0-9Xx]", "", issn or "")
    if len(raw) == 8:
        return f"{raw[:4]}-{raw[4:8]}".upper()
    return (issn or "").strip()


def _openalex_tier_from_stats(
    h_index: Any,
    mean_citedness: Any,
    works_count: Any,
) -> str:
    """Heuristic venue strength when Scimago quartile is missing (not a Q1–Q4 replacement)."""
    try:
        h = int(h_index) if h_index is not None else 0
    except (TypeError, ValueError):
        h = 0
    try:
        c2 = float(mean_citedness) if mean_citedness is not None else 0.0
    except (TypeError, ValueError):
        c2 = 0.0
    try:
        wc = int(works_count) if works_count is not None else 0
    except (TypeError, ValueError):
        wc = 0

    if h >= 70 or c2 >= 2.5 or wc >= 40000:
        return "strong"
    if h >= 28 or c2 >= 1.0 or wc >= 8000:
        return "medium"
    if h >= 10 or c2 >= 0.35 or wc >= 1500:
        return "modest"
    return "weak"

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


def _crossref_headers() -> dict[str, str]:
    """Crossref requests a contact in User-Agent; reuse OpenAlex mailto when set."""
    mail = os.getenv("TALASH_OPENALEX_MAILTO", os.getenv("TALASH_CROSSREF_MAILTO", "")).strip()
    ua = "TALASH/1.0 (https://github.com; academic CV enrichment)"
    if mail:
        ua += f" mailto:{mail}"
    return {"User-Agent": ua}


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
        async with session.get(
            "https://api.crossref.org/works",
            params=params, headers=_crossref_headers(),
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
        url = _openalex_append_mailto("https://api.openalex.org/works")
        async with session.get(
            url,
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

async def _fetch_openalex_journal_uncached(session: aiohttp.ClientSession, issn: str) -> dict:
    """
    OpenAlex ``GET /sources/issn:XXXX-XXXX`` (single object) — faster than filter search.
    Falls back to ``sources?filter=issn:`` if the direct id 404s.
    """
    if not issn:
        return {}
    disp = _issn_display(issn)
    headers = {"User-Agent": "TALASH/1.0 (https://github.com; research metadata enrichment)"}
    timeout = aiohttp.ClientTimeout(total=12)

    def _parse_source(src: dict) -> dict:
        stats = src.get("summary_stats") or {}
        raw_2yr = stats.get("2yr_mean_citedness")
        h_idx = stats.get("h_index")
        wc = src.get("works_count")
        tier = _openalex_tier_from_stats(h_idx, raw_2yr, wc)
        return {
            "found": True,
            "avg_citations_2yr": round(raw_2yr, 4) if raw_2yr is not None else None,
            "h_index": h_idx,
            "works_count": wc,
            "cited_by_count": src.get("cited_by_count"),
            "openalex_journal_tier": tier,
            "oa_scopus_proxy": (int(h_idx or 0) >= 12 and int(wc or 0) > 1500),
            "openalex_source_id": src.get("id"),
        }

    try:
        url = _openalex_append_mailto(f"https://api.openalex.org/sources/issn:{disp}")
        async with session.get(url, timeout=timeout, headers=headers) as r:
            if r.status == 200:
                src = await r.json(content_type=None)
                if isinstance(src, dict) and src.get("summary_stats") is not None:
                    return _parse_source(src)
        fb = _openalex_append_mailto(f"https://api.openalex.org/sources?filter=issn:{disp}&per-page=1")
        async with session.get(fb, timeout=timeout, headers=headers) as r2:
            if r2.status != 200:
                return {}
            data = await r2.json(content_type=None)
        results = data.get("results") or []
        if not results:
            return {}
        return _parse_source(results[0])
    except Exception as exc:
        logger.debug("[OpenAlex journal] %s", exc)
        return {}


async def fetch_openalex_journal(session: aiohttp.ClientSession, issn: str) -> dict:
    """Cached OpenAlex journal lookup by ISSN."""
    key = _normalize_issn_key(issn)
    if not key:
        return {}
    async with _ext_lock():
        hit = _OA_ISSN_CACHE.get(key)
    if hit is not None:
        return dict(hit)
    out = await _fetch_openalex_journal_uncached(session, issn)
    async with _ext_lock():
        _trim_cache(_OA_ISSN_CACHE)
        _OA_ISSN_CACHE[key] = out
    return dict(out)


async def fetch_doaj_by_issn(session: aiohttp.ClientSession, issn: str) -> dict:
    """
    DOAJ public search API — confirms the ISSN appears in the DOAJ journal index (no API key).
    https://doaj.org/api/docs
    """
    key = _normalize_issn_key(issn)
    if not key:
        return {"doaj_indexed": False, "doaj_hits": 0}
    async with _ext_lock():
        hit = _DOAJ_ISSN_CACHE.get(key)
    if hit is not None:
        return dict(hit)

    compact = key.upper()
    hyphen = f"{compact[:4]}-{compact[4:]}" if len(compact) == 8 else issn.strip()
    urls = [
        f"https://doaj.org/api/search/journals/issn:{quote(hyphen)}",
        f"https://doaj.org/api/search/journals/issn:{quote(compact)}",
    ]
    headers = {"User-Agent": "TALASH/1.0 (journal presence check; contact via project maintainer)"}
    out: dict[str, Any] = {"doaj_indexed": False, "doaj_hits": 0}
    try:
        for url in urls:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status != 200:
                    continue
                data = await r.json(content_type=None)
            total = data.get("total")
            try:
                n = int(total) if total is not None else 0
            except (TypeError, ValueError):
                n = 0
            if n > 0:
                out = {"doaj_indexed": True, "doaj_hits": n}
                break
    except Exception as exc:
        logger.debug("[DOAJ] %s", exc)

    async with _ext_lock():
        _trim_cache(_DOAJ_ISSN_CACHE)
        _DOAJ_ISSN_CACHE[key] = out
    return dict(out)


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
        async with session.get(
            f"https://api.crossref.org/works/{doi}",
            headers=_crossref_headers(),
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
            url = _openalex_append_mailto(
                "https://api.openalex.org/works"
                f"?filter=primary_location.source.display_name.search:{q}"
                "&sort=publication_year:asc&per-page=1"
            )
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
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

    enable_wos = os.getenv("TALASH_ENABLE_WOS_SCRAPE", "0").strip().lower() in ("1", "true", "yes")
    if enable_wos:
        wos, oa, cr, doaj = await asyncio.gather(
            fetch_wos_info(session, issn),
            fetch_openalex_journal(session, issn),
            fetch_crossref_doi(session, doi, candidate_name),
            fetch_doaj_by_issn(session, issn),
        )
    else:
        oa, cr, doaj = await asyncio.gather(
            fetch_openalex_journal(session, issn),
            fetch_crossref_doi(session, doi, candidate_name),
            fetch_doaj_by_issn(session, issn),
        )
        wos = {"wos_indexed": False, "impact_factor": None}

    # impact_factor: WoS scrape when enabled; else use OpenAlex 2yr mean citedness as numeric signal
    impact_factor = wos.get("impact_factor") if wos.get("impact_factor") is not None else oa.get("avg_citations_2yr")

    pub.update({
        "wos_indexed": wos.get("wos_indexed", False),
        "impact_factor": impact_factor,
        "avg_citations_2yr": oa.get("avg_citations_2yr"),
        "h_index": oa.get("h_index"),
        "works_count": oa.get("works_count"),
        "cited_by_count": oa.get("cited_by_count"),
        "openalex_journal_tier": oa.get("openalex_journal_tier", "weak"),
        "oa_scopus_proxy": oa.get("oa_scopus_proxy", False),
        "doaj_indexed": bool(doaj.get("doaj_indexed")),
        "doaj_hits": int(doaj.get("doaj_hits") or 0),
        "crossref_found": cr.get("found", False),
        "authorship_role_api": cr.get("role", "unknown"),
        "publisher_cr": cr.get("publisher", ""),
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
    max_concurrent: int | None = None,
) -> tuple[list[dict], list[dict], dict]:
    """
    Run all enrichment tasks concurrently.
    Returns (enriched_journals, enriched_conferences, audit_dict).

    audit_dict keys: skipped (bool), warnings (list[str]), errors (list[str]),
    publications_attempted (int), publications_enriched_ok (int).
    """
    audit: dict = {
        "skipped": False,
        "warnings": [],
        "errors": [],
        "publications_attempted": 0,
        "publications_enriched_ok": 0,
    }
    total = len(journals) + len(conferences)
    if total == 0:
        return [], [], audit

    if max_concurrent is None:
        try:
            max_concurrent = int(os.getenv("TALASH_ENRICHMENT_CONCURRENCY", "5") or "5")
        except ValueError:
            max_concurrent = 5
    max_concurrent = max(1, min(int(max_concurrent), 25))

    skip_gt = int(os.getenv("TALASH_SKIP_ENRICHMENT_IF_PUBS_GT", "150") or "150")
    if total > skip_gt:
        audit["skipped"] = True
        audit["warnings"].append(
            f"Skipped network enrichment: {total} publications exceed TALASH_SKIP_ENRICHMENT_IF_PUBS_GT={skip_gt}. "
            "Scores use CV metadata only."
        )
        return [dict(p) for p in journals], [dict(p) for p in conferences], audit

    audit["publications_attempted"] = total

    connector = aiohttp.TCPConnector(limit=max_concurrent, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        journal_tasks = [enrich_journal_pub(dict(p), session, candidate_name) for p in journals]
        conf_tasks = [enrich_conference_pub(dict(p), session, candidate_name) for p in conferences]
        results = await asyncio.gather(*(journal_tasks + conf_tasks), return_exceptions=True)

    n = len(journals)
    out_j: list[dict] = []
    out_c: list[dict] = []
    ok = 0
    for i, r in enumerate(results[:n]):
        if isinstance(r, Exception):
            audit["errors"].append(f"journal id={journals[i].get('id')}: {r!s}")
            out_j.append(dict(journals[i]))
        else:
            out_j.append(r)
            ok += 1
    for i, r in enumerate(results[n:]):
        if isinstance(r, Exception):
            audit["errors"].append(f"conference id={conferences[i].get('id')}: {r!s}")
            out_c.append(dict(conferences[i]))
        else:
            out_c.append(r)
            ok += 1

    audit["publications_enriched_ok"] = ok
    if audit["errors"]:
        audit["warnings"].append(
            f"{len(audit['errors'])} publication(s) failed enrichment; scoring uses partial metadata."
        )
    return out_j, out_c, audit
