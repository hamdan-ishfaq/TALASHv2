from __future__ import annotations

from typing import Any, TypeVar
import logging
import re

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
        self.provider = getattr(llm_router, "provider", "litellm-router")
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
        try:
            return self.client.chat.completions.create(
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
        except Exception as exc:
            logger.error(
                "Structured extraction failed for %s on %s: %s",
                response_model.__name__,
                self.provider,
                str(exc),
            )
            return None

    def extract_section(self, cv_text: str, section: str) -> BaseModel:
        """Run a focused extraction for one section."""
        sanitized_text = self._sanitize_cv_text(cv_text)
        contact_hints = self._extract_contact_hints(sanitized_text)
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
                    "contact details, education chronology, and work timeline integrity."
                ),
                user_prompt=base_user_prompt,
                max_tokens=2400,
                timeout=180,
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
                    "explicit evidence in the text."
                ),
                user_prompt=base_user_prompt,
                max_tokens=2200,
                timeout=180,
            ) or AcademicProfileExtraction(publications=[], supervision=[], books=[])

        if section_key == "skills":
            return self._structured_extract(
                SkillsAndIPExtraction,
                system_prompt=(
                    "You are a technical evaluator focused on concrete skill extraction and intellectual "
                    "property. Extract skills with evidence quality and all patent records."
                ),
                user_prompt=base_user_prompt,
                max_tokens=1800,
                timeout=180,
            ) or SkillsAndIPExtraction(patents=[], skills=[])

        raise ValueError(f"Unknown extraction section: {section}")

    def extract_cv_data(self, cv_text: str) -> CandidateExtraction:
        """
        Logical split extraction in 3 calls to reduce output size and truncation risk.
        """
        sanitized_text = self._sanitize_cv_text(cv_text)
        contact_hints = self._extract_contact_hints(sanitized_text)

        # Explicitly refresh routed client as requested for each extraction run.
        self.client, self.model = llm_router.get_structured_client()

        core = self.extract_section(sanitized_text, "core")
        academic = self.extract_section(sanitized_text, "academic")
        skills_and_ip = self.extract_section(sanitized_text, "skills")

        assembled = self.aggregate_sections(cv_text, core, academic, skills_and_ip)

        logger.info(
            "Logical split extraction complete | name=%s | edu=%d | exp=%d | journals=%d | conf=%d | supervision=%d | books=%d | patents=%d | skills=%d",
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
            patents=skills_and_ip.patents,
            skills=skills_and_ip.skills,
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
