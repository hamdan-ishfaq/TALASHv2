from __future__ import annotations

from pathlib import Path
from typing import Iterable

import fitz
import pdfplumber


def _clean_lines(lines: Iterable[str]) -> str:
    """Normalize whitespace and remove empty lines for stable LLM input."""
    cleaned = []
    for line in lines:
        normalized = " ".join(line.split())
        if normalized:
            cleaned.append(normalized)
    return "\n".join(cleaned)


def _extract_text_with_fitz(pdf_path: Path) -> str:
    text_chunks: list[str] = []
    with fitz.open(pdf_path) as document:
        for page in document:
            page_text = page.get_text("text") or ""
            if page_text.strip():
                text_chunks.append(page_text)
    return "\n".join(text_chunks)


def _extract_tables_with_pdfplumber(pdf_path: Path) -> str:
    table_chunks: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table_index, table in enumerate(tables, start=1):
                rows: list[str] = []
                for raw_row in table:
                    row = [((cell or "").strip()) for cell in raw_row]
                    if any(cell for cell in row):
                        rows.append(" | ".join(row))
                if rows:
                    table_chunks.append(
                        f"[TABLE page={page_number} index={table_index}]\n"
                        + "\n".join(rows)
                    )
    return "\n\n".join(table_chunks)


def extract_pdf_text(pdf_path: str | Path) -> str:
    """
    Hybrid PDF parser:
    1) Pull narrative/raw text from all pages with PyMuPDF (fitz).
    2) Pull table-like structures with pdfplumber.
    3) Merge into one cleaned string for downstream LLM extraction.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    fitz_text = _extract_text_with_fitz(path)
    table_text = _extract_tables_with_pdfplumber(path)

    merged_parts = [
        "=== RAW_TEXT (PyMuPDF) ===",
        fitz_text,
    ]
    if table_text:
        merged_parts.extend(["", "=== TABLE_TEXT (pdfplumber) ===", table_text])

    return _clean_lines("\n".join(merged_parts).splitlines())
