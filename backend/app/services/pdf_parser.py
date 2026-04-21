from __future__ import annotations

from pathlib import Path
from typing import Iterable

import fitz
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)


def _clean_lines(lines: Iterable[str]) -> str:
    """Normalize whitespace and remove empty lines for stable LLM input."""
    cleaned = []
    for line in lines:
        # PostgreSQL text columns cannot store NUL bytes.
        line = line.replace("\x00", "")
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


def _extract_text_with_ocr(pdf_path: Path) -> str:
    """
    Extract text from image-only PDFs using Tesseract OCR.
    Falls back gracefully if OCR is not available.
    """
    try:
        # Convert PDF pages to images
        images = convert_from_path(str(pdf_path), dpi=300)
        ocr_chunks: list[str] = []
        
        for page_num, image in enumerate(images, start=1):
            try:
                # Extract text from image using Tesseract
                text = pytesseract.image_to_string(image, lang="eng")
                if text.strip():
                    ocr_chunks.append(f"[OCR_PAGE_{page_num}]\n{text}")
            except Exception as e:
                logger.warning(f"OCR failed for page {page_num}: {str(e)}")
                continue
        
        if ocr_chunks:
            return "\n".join(ocr_chunks)
        else:
            logger.warning("OCR extraction yielded no text")
            return ""
    
    except Exception as e:
        logger.warning(f"OCR processing failed: {str(e)}. Tesseract may not be installed.")
        return ""


def _is_image_only_pdf(pdf_path: Path) -> bool:
    """
    Detect if PDF contains mostly images (text < 10% of content).
    Image-only PDFs need OCR processing.
    """
    try:
        with fitz.open(pdf_path) as document:
            total_chars = 0
            for page in document:
                text = page.get_text("text") or ""
                total_chars += len(text.strip())
            
            # If very little text extracted, likely image-only
            return total_chars < 100
    except Exception as e:
        logger.warning(f"Error detecting image-only PDF: {str(e)}")
        return False


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
    Hybrid PDF parser with OCR support:
    1) Pull narrative/raw text from all pages with PyMuPDF (fitz).
    2) If PDF is image-only (low text content), use Tesseract OCR.
    3) Pull table-like structures with pdfplumber.
    4) Merge into one cleaned string for downstream LLM extraction.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    # Try standard text extraction first
    fitz_text = _extract_text_with_fitz(path)
    
    # Check if PDF is image-only and needs OCR
    if _is_image_only_pdf(path):
        logger.info(f"Image-only PDF detected: {path.name}. Applying OCR...")
        ocr_text = _extract_text_with_ocr(path)
        if ocr_text:
            fitz_text = ocr_text
    
    table_text = _extract_tables_with_pdfplumber(path)

    merged_parts = [
        "=== RAW_TEXT (PyMuPDF/OCR) ===",
        fitz_text,
    ]
    if table_text:
        merged_parts.extend(["", "=== TABLE_TEXT (pdfplumber) ===", table_text])

    return _clean_lines("\n".join(merged_parts).splitlines())
