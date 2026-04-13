"""Page-by-page CV extraction to handle large documents with limited context window."""

import logging
from typing import Any

import pdfplumber

from app.services.extractor import CVExtractorService, Candidate as ExtractedCandidate
from app.services.pdf_parser import extract_pdf_text

logger = logging.getLogger(__name__)


class PageByPageExtractor:
    """Extract CV data page-by-page to handle limited context window (2048 tokens)."""

    def __init__(self, pdf_path: str, model: str = "llama3.1", ollama_host: str = "http://host.docker.internal:11434"):
        self.pdf_path = pdf_path
        self.model = model
        self.ollama_host = ollama_host
        self.extractor = CVExtractorService(ollama_host=ollama_host, model=model)

    def _extract_page_text(self, page_num: int) -> str:
        """Extract text from a specific PDF page."""
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                if page_num >= len(pdf.pages):
                    return ""
                page = pdf.pages[page_num]
                text = page.extract_text() or ""
                logger.debug(f"[PAGE-EXTRACT] Page {page_num + 1}: {len(text)} chars")
                return text
        except Exception as e:
            logger.error(f"[PAGE-EXTRACT-ERROR] Failed to extract page {page_num}: {e}")
            return ""

    def _get_page_count(self) -> int:
        """Get total number of pages in PDF."""
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                return len(pdf.pages)
        except Exception as e:
            logger.error(f"[PAGE-COUNT-ERROR] {e}")
            return 0

    def _extract_page_data(self, page_text: str, page_num: int) -> ExtractedCandidate:
        """Extract structured data from a single page."""
        if not page_text.strip():
            return ExtractedCandidate()

        prompt = f"""
Extract CV data from this page ({page_num}).
Focus on: Personal info, Education, Experience, Publications, Skills, Patents, Books, and Supervision records found on THIS page.
Return only data present on this page.

FORMAT REQUIREMENTS (CRITICAL):
- publications[].authors: LIST OF STRINGS ONLY ['Author 1', 'Author 2'], NOT [{{'name': 'Author'}}]
- publications[].venue: STRING like 'IEEE Journal', NEVER integer/number
- years: 4-digit integers like 2023, NEVER decimals or text
- All string fields: plain text, NOT nested objects

PAGE {page_num} TEXT:
{page_text}
""".strip()

        try:
            logger.debug(f"[PAGE-{page_num}] Sending to LLM for extraction")
            result = self.extractor._extract_pass(prompt).candidate
            logger.info(f"[PAGE-{page_num}-OK] Edu: {len(result.education)}, Exp: {len(result.experience)}, Pub: {len(result.publications)}")
            return result
        except Exception as e:
            logger.warning(f"[PAGE-{page_num}-FAIL] {e}")
            return ExtractedCandidate()

    def extract_all_pages(self) -> ExtractedCandidate:
        """Extract data from all pages and merge results."""
        page_count = self._get_page_count()
        logger.info(f"[PAGE-EXTRACTION] Starting page-by-page extraction | Total pages: {page_count}")

        merged = ExtractedCandidate()
        seen_education = set()
        seen_experience = set()
        seen_skills = set()
        seen_patents = set()
        seen_books = set()

        for page_num in range(page_count):
            logger.info(f"[PAGE-{page_num + 1}/{page_count}] Processing")
            page_text = self._extract_page_text(page_num)

            if not page_text.strip():
                logger.debug(f"[PAGE-{page_num + 1}] Empty, skipping")
                continue

            page_data = self._extract_page_data(page_text, page_num + 1)

            # Merge name/email from first page with data
            if page_num == 0 and page_data.name:
                merged.name = page_data.name
            if page_num == 0 and page_data.email:
                merged.email = page_data.email

            # Merge education - avoid duplicates
            for edu in page_data.education:
                key = (
                    (edu.degree or "").lower(),
                    (edu.institution or "").lower(),
                    edu.year,
                )
                if key not in seen_education:
                    merged.education.append(edu)
                    seen_education.add(key)

            # Merge experience - avoid duplicates
            for exp in page_data.experience:
                key = (
                    (exp.job_title or "").lower(),
                    (exp.organization or "").lower(),
                )
                if key not in seen_experience:
                    merged.experience.append(exp)
                    seen_experience.add(key)

            # Merge publications
            merged.publications.extend(page_data.publications)

            # Merge skills - avoid duplicates
            if hasattr(page_data, 'skills') and page_data.skills:
                for skill in page_data.skills:
                    key = (skill.name or "").lower()
                    if key not in seen_skills:
                        merged.skills.append(skill)
                        seen_skills.add(key)

            # Merge patents - avoid duplicates
            if hasattr(page_data, 'patents') and page_data.patents:
                for patent in page_data.patents:
                    key = (patent.title or "").lower()
                    if key not in seen_patents:
                        merged.patents.append(patent)
                        seen_patents.add(key)

            # Merge books - avoid duplicates
            if hasattr(page_data, 'books') and page_data.books:
                for book in page_data.books:
                    key = (book.title or "").lower()
                    if key not in seen_books:
                        merged.books.append(book)
                        seen_books.add(key)

            # Merge supervision records
            if hasattr(page_data, 'supervision') and page_data.supervision:
                merged.supervision.extend(page_data.supervision)

        logger.info(f"[PAGE-EXTRACTION-COMPLETE] Final counts | Name: {merged.name} | Edu: {len(merged.education)} | Exp: {len(merged.experience)} | Pub: {len(merged.publications)} | Skills: {len(merged.skills)} | Patents: {len(merged.patents)} | Books: {len(merged.books)} | Supervision: {len(merged.supervision)}")
        return merged
