"""
Heuristic column detection for QS / THE style institution ranking workbooks.
Falls back to legacy layout: data from row 3, columns (1-based) seq, rank, prior rank,
Institution, Location mapped to 0-based indices 0,1,2,3,4.
"""
from __future__ import annotations

import logging
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


def _norm_cell(c) -> str:
    if c is None:
        return ""
    return str(c).strip().lower()


def detect_ranking_layout(rows: list[tuple]) -> Optional[tuple[int, list[int], int, Optional[int], int]]:
    """
    Returns (header_row_index 0-based, rank_col_indices sorted, institution_col,
             country_col or None, first_data_row 0-based) or None for legacy layout.
    """
    for ri, row in enumerate(rows[:22]):
        if not row:
            continue
        headers: list[tuple[int, str]] = []
        for j, cell in enumerate(row):
            t = _norm_cell(cell)
            if t:
                headers.append((j, t))

        rank_cols: list[int] = []
        inst_cols: list[int] = []
        country_cols: list[int] = []
        for j, t in headers:
            if "rank" in t and "reputation" not in t and "employer" not in t and "salary" not in t:
                rank_cols.append(j)
            if any(k in t for k in ("institution", "university")) and "country" not in t:
                inst_cols.append(j)
            if "country" in t or t in ("location", "region", "country / region"):
                country_cols.append(j)
            if t == "name" and not inst_cols:
                inst_cols.append(j)

        if not inst_cols or not rank_cols:
            continue

        rank_cols = sorted(set(rank_cols))
        inst_col = inst_cols[0]
        for j in inst_cols:
            ht = next((t for jj, t in headers if jj == j), "")
            if "institution" in ht:
                inst_col = j
                break

        country_col = country_cols[0] if country_cols else None
        return ri, rank_cols, inst_col, country_col, ri + 1

    return None


def iter_ranking_rows(ws, legacy_min_data_row: int = 3) -> Iterator[tuple[str, str, str | None, str | None]]:
    """
    Yield (institution, rank_primary, rank_secondary, country).
    rank_secondary may be None if workbook has a single rank column.
    """
    rows = list(ws.iter_rows(min_row=1, max_row=500, values_only=True))
    if not rows:
        return

    detected = detect_ranking_layout(rows)
    if detected is None:
        for row in rows[legacy_min_data_row - 1 :]:
            if not row or len(row) < 4 or row[3] is None:
                continue
            inst = str(row[3]).strip()
            if not inst:
                continue
            r2026 = row[1] if len(row) > 1 else None
            r2025 = row[2] if len(row) > 2 else None
            loc = str(row[4]) if len(row) > 4 and row[4] else None
            yield (
                inst,
                str(r2026).strip() if r2026 is not None else "",
                str(r2025).strip() if r2025 is not None else None,
                loc,
            )
        return

    _hdr_i, rank_cols, inst_col, country_col, first_data = detected
    logger.info(
        "Ranking XLSX autodetect: header_row=%s rank_cols=%s inst_col=%s country_col=%s first_data_row=%s",
        detected[0] + 1,
        [c + 1 for c in rank_cols],
        inst_col + 1,
        (country_col + 1) if country_col is not None else None,
        first_data + 1,
    )

    rank_primary = rank_cols[0]
    rank_secondary = rank_cols[1] if len(rank_cols) > 1 else None

    for row in rows[first_data:]:
        if not row or len(row) <= inst_col:
            continue
        inst = row[inst_col]
        if inst is None:
            continue
        inst_s = str(inst).strip()
        if not inst_s:
            continue
        rp = row[rank_primary] if len(row) > rank_primary else None
        rp_s = str(rp).strip() if rp is not None else ""
        rs_s: str | None = None
        if rank_secondary is not None and len(row) > rank_secondary:
            rs = row[rank_secondary]
            rs_s = str(rs).strip() if rs is not None else None
        loc: str | None = None
        if country_col is not None and len(row) > country_col and row[country_col] is not None:
            loc = str(row[country_col]).strip() or None
        yield inst_s, rp_s, rs_s, loc
