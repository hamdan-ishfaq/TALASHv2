from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, TypeVar

from pydantic import BaseModel

from app.schemas.extraction import (
    AcademicProfileExtraction,
    CandidateExtraction,
    CoreProfileExtraction,
    SkillsAndIPExtraction,
)
from app.services.llm_router import llm_router

logger = logging.getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)

# ---------------------------------------------------------------------------
# OpenRouter Free-Tier Rate-Limit Safety
# ---------------------------------------------------------------------------
# Configurable delay (seconds) between sequential LLM calls.
# Default 5s keeps us well within OpenRouter free-tier RPM limits (~10-20 RPM).
OPENROUTER_INTER_REQUEST_DELAY = int(
    os.getenv("OPENROUTER_INTER_REQUEST_DELAY", "5")
)

# Cap CV characters sent to the LLM (large PDFs slow requests and risk truncation errors).
TALASH_MAX_CV_CHARS = int(os.getenv("TALASH_MAX_CV_CHARS", "120000"))

# ---------------------------------------------------------------------------
# Pre-validation normaliser – coerces null → [] for known list-typed fields
# in raw LLM JSON *before* Pydantic sees it.  Belt-and-suspenders with the
# ``_NullListCoercionMixin`` on the schema classes themselves.
# ---------------------------------------------------------------------------
_NULL_TO_LIST_FIELDS = frozenset({
    "keywords", "author_affiliations", "publications", "supervision",
    "books", "patents", "skills", "education", "experience",
    "education_records", "work_experiences", "journal_publications",
    "conference_publications", "supervision_records", "career_breaks"
})


def normalize_nulls(obj):
    """Recursively coerce ``null`` → ``[]`` for known list fields.

    Call this on the raw dict / JSON-parsed output from the LLM **before**
    passing it into ``model_validate()``.  This catches edge-cases where the
    model returns explicit ``null`` values for list-typed keys.
    """
    if isinstance(obj, dict):
        return {
            k: ([] if v is None and k in _NULL_TO_LIST_FIELDS else normalize_nulls(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [normalize_nulls(i) for i in obj]
    return obj


EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{1,4}\)?[\s.-]?)?\d[\d\s().-]{6,}\d(?!\w)"
)
LINKEDIN_PATTERN = re.compile(
    r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/[A-Za-z0-9\-_/?.=&%]+",
    flags=re.IGNORECASE,
)
RAW_TEXT_HEADER_PATTERN = re.compile(r"^\s*=+\s*RAW_TEXT(?:\s*\([^\)]*\))?\s*=+\s*$", re.IGNORECASE)
PAGE_NUMBER_PATTERN = re.compile(r"^\s*(?:page\s*)?\d+(?:\s*/\s*\d+)?\s*$", re.IGNORECASE)
STRUCTURAL_ARTIFACT_PATTERN = re.compile(
    r"^\s*(?:---+|___+|\*\*\*+|\|\s*\|.*\|\s*\|)\s*$"
)


class CVExtractorService:
    def __init__(self):
        self.client, self.model = llm_router.get_structured_client()
        self.provider = getattr(llm_router, "provider", "openrouter")
        logger.info(
            "CVExtractorService initialized | Model: %s | Provider: %s",
            self.model,
            self.provider,
        )

    @staticmethod
    def _clean_phone(raw_phone: str | None) -> str | None:
        if not raw_phone:
            return None
        compact = re.sub(r"\s+", " ", raw_phone).strip()
        compact = compact.rstrip(".,;:")
        return compact

    @staticmethod
    def _sanitize_cv_text(cv_text: str) -> str:
        """Remove parser/debug artifacts before any LLM call is made."""
        cleaned_lines: list[str] = []
        for raw_line in cv_text.splitlines():
            line = raw_line.replace("\x00", "").rstrip()
            stripped = line.strip()
            if not stripped:
                cleaned_lines.append("")
                continue
            if RAW_TEXT_HEADER_PATTERN.match(stripped):
                continue
            if PAGE_NUMBER_PATTERN.match(stripped):
                continue
            if STRUCTURAL_ARTIFACT_PATTERN.match(stripped):
                continue
            if re.fullmatch(r"[-_=]{10,}", stripped):
                continue
            cleaned_lines.append(line)
        sanitized = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines)).strip()
        return sanitized

    @staticmethod
    def _truncate_cv_text(cv_text: str, max_chars: int | None = None) -> str:
        """Keep head + tail so contact lines at the top and publications at the end stay visible."""
        limit = max_chars if max_chars is not None else TALASH_MAX_CV_CHARS
        if limit <= 0 or len(cv_text) <= limit:
            return cv_text
        head = max(8_000, int(limit * 0.62))
        tail = limit - head - 120
        if tail < 4_000:
            return cv_text[:limit] + "\n\n[CV text truncated for model context]\n"
        mid = "\n\n...[middle of CV omitted for size / token limits]...\n\n"
        return cv_text[:head] + mid + cv_text[-tail:]

    @staticmethod
    def _journal_pub_key(j: Any) -> tuple:
        doi = (getattr(j, "doi", None) or "").strip().lower()
        if doi and len(doi) > 6:
            return ("doi", doi)
        title = re.sub(r"\s+", " ", (getattr(j, "title", None) or "").lower()).strip()[:240]
        jn = (getattr(j, "journal_name", None) or "").lower().strip()[:120]
        return ("t", title, getattr(j, "year", None), jn)

    @staticmethod
    def _conference_pub_key(c: Any) -> tuple:
        doi = (getattr(c, "doi", None) or "").strip().lower()
        if doi and len(doi) > 6:
            return ("doi", doi)
        title = re.sub(r"\s+", " ", (getattr(c, "title", None) or "").lower()).strip()[:240]
        cn = (getattr(c, "conference_name", None) or "").lower().strip()[:120]
        return ("t", title, getattr(c, "year", None), cn)

    @staticmethod
    def _dedupe_journals(items: list[Any]) -> list[Any]:
        seen: set[tuple] = set()
        out: list[Any] = []
        for j in items:
            k = CVExtractorService._journal_pub_key(j)
            if k in seen:
                continue
            seen.add(k)
            out.append(j)
        return out

    @staticmethod
    def _dedupe_conferences(items: list[Any]) -> list[Any]:
        seen: set[tuple] = set()
        out: list[Any] = []
        for c in items:
            k = CVExtractorService._conference_pub_key(c)
            if k in seen:
                continue
            seen.add(k)
            out.append(c)
        return out

    @staticmethod
    def _dedupe_skills(items: list[Any]) -> list[Any]:
        seen: set[str] = set()
        out: list[Any] = []
        for s in items:
            k = re.sub(r"\s+", " ", (getattr(s, "name", None) or "").lower()).strip()[:160]
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(s)
        return out

    @staticmethod
    def _dedupe_patents(items: list[Any]) -> list[Any]:
        seen: set[tuple] = set()
        out: list[Any] = []
        for p in items:
            pn = (getattr(p, "patent_no", None) or "").strip().lower()
            key: tuple = ("n", pn) if pn else ("t", (getattr(p, "title", None) or "").lower().strip()[:200])
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        return out

    @staticmethod
    def _extract_contact_hints(cv_text: str) -> dict[str, str | None]:
        email_match = EMAIL_PATTERN.search(cv_text)
        phone_match = PHONE_PATTERN.search(cv_text)
        linkedin_match = LINKEDIN_PATTERN.search(cv_text)

        linkedin_url = None
        if linkedin_match:
            linkedin_url = linkedin_match.group(0).strip()
            if not linkedin_url.lower().startswith("http"):
                linkedin_url = f"https://{linkedin_url}"

        return {
            "email": email_match.group(0).strip() if email_match else None,
            "phone": CVExtractorService._clean_phone(phone_match.group(0)) if phone_match else None,
            "linkedin_url": linkedin_url,
        }

    @staticmethod
    def _extract_contact_info_regex(text: str) -> dict[str, str | None]:
        """Aggressively hunt for contact info using regex to override LLM hallucinations."""
        reference_split = re.split(r"\breferences?\b", text, maxsplit=1, flags=re.IGNORECASE)
        search_zone = reference_split[0][:2000]

        email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", search_zone)
        email = email_match.group(0) if email_match else None

        phone_match = re.search(
            r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}",
            search_zone,
        )
        phone = CVExtractorService._clean_phone(phone_match.group(0)) if phone_match else None

        linkedin_match = re.search(
            r"(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_-]+)",
            search_zone,
            re.IGNORECASE,
        )
        linkedin_url = (
            f"https://www.linkedin.com/in/{linkedin_match.group(1)}" if linkedin_match else None
        )

        return {
            "email": email,
            "phone": phone,
            "linkedin_url": linkedin_url,
        }

    @staticmethod
    def _first_clean_capitalized_phrase(cv_text: str) -> str:
        for line in cv_text.splitlines()[:40]:
            token = re.sub(r"\s+", " ", line).strip()
            if not token:
                continue
            if any(marker in token.lower() for marker in ["raw_text", "page", "curriculum vitae", "resume"]):
                continue
            if len(token) > 90:
                continue
            if re.search(r"[A-Za-z]", token) and token == token.title():
                return token
            if re.fullmatch(r"[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){1,4}", token):
                return token
        return "Unknown Candidate"

    @staticmethod
    def _is_malformed_name(name: str | None) -> bool:
        """Check if a name appears to be malformed or a debug header."""
        if not name:
            return False
        name_lower = name.lower()
        suspicious_patterns = [
            "===",
            "raw_text",
            "page ",
            "pdfmupdf",
            "ocr",
            "extraction",
            "failed",
            "error",
            "none",
            "null",
            "[",
            "{",
            "pdfplumber",
            "text layer",
        ]
        return any(pattern in name_lower for pattern in suspicious_patterns) or len(name.strip()) > 90

    @staticmethod
    def _guess_name_from_text(cv_text: str) -> str:
        return CVExtractorService._first_clean_capitalized_phrase(cv_text)

    def _structured_extract(
        self,
        response_model: type[TModel],
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        timeout: int,
    ) -> TModel | None:
        """Perform a structured extraction call via instructor + OpenRouter.

        Records attempt/success/failure metrics on the global llm_router
        for observability.
        """
        request_id = llm_router.record_attempt()
        started_at = time.time()

        logger.info(
            "[LLM-REQUEST #%d] model=%s | schema=%s | max_tokens=%d | timeout=%ds",
            request_id,
            self.model,
            response_model.__name__,
            max_tokens,
            timeout,
        )

        try:
            result = self.client.chat.completions.create(
                model=self.model,
                response_model=response_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_retries=2,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            duration = time.time() - started_at
            llm_router.record_success(
                request_id,
                duration,
                response_preview=f"OK: {response_model.__name__}",
            )
            logger.info(
                "[LLM-RESPONSE #%d] model=%s | schema=%s | duration=%.2fs | status=SUCCESS",
                request_id,
                self.model,
                response_model.__name__,
                duration,
            )
            return result

        except Exception as exc:
            duration = time.time() - started_at
            error_text = f"{type(exc).__name__}: {exc}"
            llm_router.record_failure(request_id, duration, error_text)
            logger.error(
                "[LLM-ERROR #%d] model=%s | schema=%s | duration=%.2fs | error=%s",
                request_id,
                self.model,
                response_model.__name__,
                duration,
                error_text,
            )
            return None

    def extract_section(
        self,
        cv_text: str,
        section: str,
        *,
        contact_source: str | None = None,
    ) -> BaseModel:
        """Run a focused extraction for one section.

        ``contact_source`` (optional) is the full sanitized CV used for regex contact hints
        while ``cv_text`` is what is sent to the model (may be truncated for very large PDFs).
        """
        sanitized_text = self._sanitize_cv_text(cv_text)
        contact_src = (
            self._sanitize_cv_text(contact_source) if contact_source is not None else sanitized_text
        )
        contact_hints = self._extract_contact_hints(contact_src)
        base_user_prompt = (
            "Extract only what is explicitly present in the sanitized CV text. "
            "Do not hallucinate or infer unsupported facts. "
            "Return only the schema for this section.\n\n"
            f"CV text:\n{sanitized_text}"
        )

        section_key = section.strip().lower()
        if section_key == "core":
            model = self._structured_extract(
                CoreProfileExtraction,
                system_prompt=(
                    "You are a senior HR timeline extraction engine. Focus on core profile facts, "
                    "contact details, education chronology, and work timeline integrity. "
                    "CRITICAL: For ALL list-type fields (education, experience) you MUST "
                    "return an empty array [] — NEVER return null or None for any list field."
                ),
                user_prompt=base_user_prompt,
                max_tokens=4096,
                timeout=300,
            ) or CoreProfileExtraction(
                name=self._guess_name_from_text(sanitized_text),
                email=contact_hints["email"],
                phone=contact_hints["phone"],
                linkedin_url=contact_hints["linkedin_url"],
                education=[],
                experience=[],
            )
            if self._is_malformed_name(model.name):
                model.name = self._first_clean_capitalized_phrase(sanitized_text)
            if not model.email:
                model.email = contact_hints["email"]
            if not model.phone:
                model.phone = contact_hints["phone"]
            if not model.linkedin_url:
                model.linkedin_url = contact_hints["linkedin_url"]
            return model

        if section_key == "academic":
            return self._structured_extract(
                AcademicProfileExtraction,
                system_prompt=(
                    "You are an academic profile reviewer. Extract publications with citation-quality "
                    "metadata, author order, and venue details. Also extract supervision and books. "
                    "Each publication bundle should populate exactly one field: journal or conference. "
                    "Publications may appear as flattened text from PDF tables. Look for paper titles "
                    "followed by journal/conference names, volumes/issues, pages, and years. Even when "
                    "headers and rows are merged, reconstruct publication records conservatively from "
                    "explicit evidence in the text.\n\n"
                    "CRITICAL: For ALL list-type fields (keywords, author_affiliations, publications, "
                    "supervision, books) you MUST return an empty array [] — NEVER return null or None "
                    "for any list field."
                ),
                user_prompt=base_user_prompt,
                max_tokens=4096,
                timeout=300,
            ) or AcademicProfileExtraction(publications=[], supervision=[], books=[])

        if section_key == "skills":
            return self._structured_extract(
                SkillsAndIPExtraction,
                system_prompt=(
                    "You are a technical evaluator focused on concrete skill extraction and intellectual "
                    "property. Extract skills with evidence quality and all patent records.\n\n"
                    "CRITICAL: For ALL list-type fields (patents, skills) you MUST return an empty "
                    "array [] — NEVER return null or None for any list field."
                ),
                user_prompt=base_user_prompt,
                max_tokens=3072,
                timeout=300,
            ) or SkillsAndIPExtraction(patents=[], skills=[])

        raise ValueError(f"Unknown extraction section: {section}")

    def extract_cv_data(self, cv_text: str) -> CandidateExtraction:
        """
        Sequential 3-call extraction with inter-request delays for OpenRouter
        free-tier rate-limit safety.

        Strategy:
          1. Core profile (contact + education + experience)
          2. Academic profile (publications + supervision + books)
          3. Skills & IP (skills + patents)

        Each call is separated by OPENROUTER_INTER_REQUEST_DELAY seconds.
        """
        sanitized_full = self._sanitize_cv_text(cv_text)
        llm_text = self._truncate_cv_text(sanitized_full)
        if len(llm_text) < len(sanitized_full):
            logger.info(
                "[EXTRACTOR] CV length %d → truncated to %d chars for LLM (TALASH_MAX_CV_CHARS=%s)",
                len(sanitized_full),
                len(llm_text),
                os.getenv("TALASH_MAX_CV_CHARS", "120000"),
            )
        # Explicitly refresh routed client for each extraction run.
        self.client, self.model = llm_router.get_structured_client()

        # --- Sequential extraction with rate-limit delays ---
        logger.info(
            "[EXTRACTOR] Starting sequential 3-section extraction | delay=%ds",
            OPENROUTER_INTER_REQUEST_DELAY,
        )

        # Section 1: Core
        core = self.extract_section(llm_text, "core", contact_source=sanitized_full)

        # Rate-limit delay before next call
        if OPENROUTER_INTER_REQUEST_DELAY > 0:
            logger.info(
                "[EXTRACTOR] Waiting %ds before academic section (rate-limit safety)...",
                OPENROUTER_INTER_REQUEST_DELAY,
            )
            time.sleep(OPENROUTER_INTER_REQUEST_DELAY)

        # Section 2: Academic
        academic = self.extract_section(llm_text, "academic", contact_source=sanitized_full)

        # Rate-limit delay before next call
        if OPENROUTER_INTER_REQUEST_DELAY > 0:
            logger.info(
                "[EXTRACTOR] Waiting %ds before skills section (rate-limit safety)...",
                OPENROUTER_INTER_REQUEST_DELAY,
            )
            time.sleep(OPENROUTER_INTER_REQUEST_DELAY)

        # Section 3: Skills & IP
        skills_and_ip = self.extract_section(llm_text, "skills", contact_source=sanitized_full)

        assembled = self.aggregate_sections(sanitized_full, core, academic, skills_and_ip)

        logger.info(
            "Sequential extraction complete | name=%s | edu=%d | exp=%d | journals=%d | conf=%d | supervision=%d | books=%d | patents=%d | skills=%d",
            assembled.name,
            len(assembled.education_records),
            len(assembled.work_experiences),
            len(assembled.journal_publications),
            len(assembled.conference_publications),
            len(assembled.supervision_records),
            len(assembled.books),
            len(assembled.patents),
            len(assembled.skills),
        )

        return assembled

    def aggregate_sections(
        self,
        cv_text: str,
        core: CoreProfileExtraction,
        academic: AcademicProfileExtraction,
        skills_and_ip: SkillsAndIPExtraction,
    ) -> CandidateExtraction:
        """Merge focused section payloads back into one candidate object."""
        sanitized_text = self._sanitize_cv_text(cv_text)
        contact_hints = self._extract_contact_hints(sanitized_text)
        contact_overrides = self._extract_contact_info_regex(sanitized_text)

        journal_publications = []
        conference_publications = []
        for publication_bundle in academic.publications:
            if publication_bundle.journal is not None:
                journal_publications.append(publication_bundle.journal)
            if publication_bundle.conference is not None:
                conference_publications.append(publication_bundle.conference)

        journal_publications = self._dedupe_journals(journal_publications)
        conference_publications = self._dedupe_conferences(conference_publications)
        patents_deduped = self._dedupe_patents(skills_and_ip.patents)
        skills_deduped = self._dedupe_skills(skills_and_ip.skills)

        extracted_name = core.name or self._guess_name_from_text(sanitized_text)
        if self._is_malformed_name(extracted_name):
            logger.warning(
                "Malformed name detected from shared aggregation: '%s' | Using fallback extraction",
                extracted_name,
            )
            extracted_name = self._first_clean_capitalized_phrase(sanitized_text)

        assembled = CandidateExtraction(
            name=extracted_name,
            email=contact_overrides["email"] or contact_hints["email"] or core.email,
            phone=contact_overrides["phone"] or contact_hints["phone"] or core.phone,
            linkedin_url=contact_overrides["linkedin_url"] or contact_hints["linkedin_url"] or core.linkedin_url,
            personal_website=core.personal_website,
            other_urls=core.other_urls,
            summary_of_profile=core.summary_of_profile,
            education_records=core.education,
            work_experiences=core.experience,
            journal_publications=journal_publications,
            conference_publications=conference_publications,
            supervision_records=academic.supervision,
            books=academic.books,
            patents=patents_deduped,
            skills=skills_deduped,
            career_breaks=[],
        )
        assembled.llm_model_name = self.model
        assembled.llm_provider = self.provider
        return assembled

    def extract(self, cv_text: str) -> CandidateExtraction:
        return self.extract_cv_data(cv_text)


def extract_cv_data(cv_text: str, **kwargs: Any) -> CandidateExtraction:
    service = CVExtractorService()
    return service.extract_cv_data(cv_text)


def extract_candidate_from_text(cv_text: str, **kwargs: Any) -> CandidateExtraction:
    service = CVExtractorService()
    return service.extract_cv_data(cv_text)
