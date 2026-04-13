from __future__ import annotations

from typing import Any
import logging
import re
from datetime import datetime

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Education(BaseModel):
    degree: str | None = None
    title: str | None = None
    institution: str | None = None
    year: int | None = None
    cgpa: float | None = None


class Experience(BaseModel):
    job_title: str | None = None
    organization: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool | None = None


class Publication(BaseModel):
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    year: int | None = None
    type: str | None = None


class Skill(BaseModel):
    name: str | None = None
    proficiency_level: str | None = None
    years_of_experience: float | None = None


class Patent(BaseModel):
    title: str | None = None
    inventors: list[str] = Field(default_factory=list)
    patent_no: str | None = None
    year: int | None = None
    status: str | None = None


class Book(BaseModel):
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    publisher: str | None = None
    year: int | None = None
    isbn: str | None = None


class SupervisionRecord(BaseModel):
    level: str | None = None
    student_name: str | None = None
    year: int | None = None


class Candidate(BaseModel):
    name: str | None = None
    email: str | None = None
    summary: str | None = None
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    patents: list[Patent] = Field(default_factory=list)
    books: list[Book] = Field(default_factory=list)
    supervision: list[SupervisionRecord] = Field(default_factory=list)


class CVExtractionResult(BaseModel):
    candidate: Candidate


def dedupe_education_rows(rows: list[Education]) -> list[Education]:
    """Remove duplicate education entries by (degree, institution, year)."""
    deduped: list[Education] = []
    seen: set[tuple[str, str, int | None]] = set()

    for row in rows:
        # Skip rows with no meaningful data
        if not row.degree and not row.institution:
            continue
        
        key = (
            (row.degree or "").strip().lower(),
            (row.institution or "").strip().lower(),
            row.year,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


def dedupe_and_clean_publications(rows: list[Publication]) -> list[Publication]:
    """Remove duplicate publications and clean noisy entries."""
    cleaned: list[Publication] = []
    seen: set[tuple[str, str, int | None]] = set()

    for row in rows:
        # Skip placeholder/empty entries
        if not row.title or row.title.lower() in ["publication", "paper", "research"]:
            continue
        
        # Clean title (remove extra spaces, normalize)
        title = (row.title or "").strip()
        if len(title) < 5:
            continue
        
        # Normalize venue (remove "journal", "conference" prefix if suspicious)
        venue = (row.venue or "").strip() if row.venue else ""
        
        # Skip if venue is numeric or clearly malformed
        if venue and (venue.isdigit() or len(venue) > 200):
            venue = ""
        
        # Normalize authors (remove empty strings)
        authors = [a.strip() for a in (row.authors or []) if a and a.strip()]
        
        key = (
            title.lower(),
            venue.lower(),
            row.year,
        )
        
        if key in seen:
            continue
        seen.add(key)
        
        cleaned.append(Publication(
            title=title,
            authors=authors,
            venue=venue if venue else None,
            year=row.year,
            type=row.type
        ))

    return cleaned


def dedupe_and_clean_experience(rows: list[Experience]) -> list[Experience]:
    """Remove duplicate experience entries and fill incomplete values."""
    cleaned: list[Experience] = []
    seen: set[tuple[str, str, str]] = set()

    for row in rows:
        # Skip placeholder entries
        if not row.job_title and not row.organization:
            continue
        
        # Clean strings
        job_title = (row.job_title or "").strip()
        org = (row.organization or "").strip()
        location = (row.location or "").strip()

        # Skip obviously malformed entries
        if len(job_title) < 2 and len(org) < 2:
            continue
        
        key = (
            job_title.lower(),
            org.lower(),
            location.lower(),
        )
        
        if key in seen:
            continue
        seen.add(key)
        
        cleaned.append(Experience(
            job_title=job_title if job_title else None,
            organization=org if org else None,
            location=location if location else None,
            start_date=row.start_date,
            end_date=row.end_date,
            is_current=row.is_current
        ))

    return cleaned


def dedupe_publications(rows: list[Publication]) -> list[Publication]:
    """Remove duplicate publications by (title, venue, year)."""
    deduped: list[Publication] = []
    seen: set[tuple[str, str, int | None]] = set()

    for row in rows:
        key = (
            (row.title or "").strip().lower(),
            (row.venue or "").strip().lower(),
            row.year,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


def dedupe_and_clean_patents(rows: list[Patent]) -> list[Patent]:
    """Remove duplicate patents and clean noisy entries."""
    cleaned: list[Patent] = []
    seen: set[tuple[str, str, int | None]] = set()

    for row in rows:
        # Skip if no title
        if not row.title or not (row.title or "").strip():
            continue
        
        title = (row.title or "").strip()
        if len(title) < 3:
            continue
        
        # Clean inventors list - ensure strings only
        inventors = []
        if row.inventors:
            for inv in row.inventors:
                if inv and isinstance(inv, str):
                    inv_clean = inv.strip()
                    if len(inv_clean) > 2:
                        inventors.append(inv_clean)
        
        # Skip if no inventors
        if not inventors:
            continue
        
        patent_no = (row.patent_no or "").strip() if row.patent_no else None
        status = (row.status or "").strip() if row.status else None
        
        key = (title.lower(), ",".join(inventors).lower(), row.year)
        if key in seen:
            continue
        seen.add(key)
        
        cleaned.append(Patent(
            title=title,
            inventors=inventors,
            patent_no=patent_no if patent_no else None,
            year=row.year,
            status=status if status else None
        ))

    return cleaned


def dedupe_and_clean_books(rows: list[Book]) -> list[Book]:
    """Remove duplicate books and clean noisy entries."""
    cleaned: list[Book] = []
    seen: set[tuple[str, str, int | None]] = set()

    for row in rows:
        # Skip if no title
        if not row.title or not (row.title or "").strip():
            continue
        
        title = (row.title or "").strip()
        if len(title) < 3:
            continue
        
        # Clean authors list - ensure strings only
        authors = []
        if row.authors:
            for auth in row.authors:
                if auth and isinstance(auth, str):
                    auth_clean = auth.strip()
                    if len(auth_clean) > 2:
                        authors.append(auth_clean)
        
        # Skip if no authors
        if not authors:
            continue
        
        publisher = (row.publisher or "").strip() if row.publisher else None
        isbn = (row.isbn or "").strip() if row.isbn else None
        
        key = (title.lower(), ",".join(authors).lower(), row.year)
        if key in seen:
            continue
        seen.add(key)
        
        cleaned.append(Book(
            title=title,
            authors=authors,
            publisher=publisher if publisher else None,
            year=row.year,
            isbn=isbn if isbn else None
        ))

    return cleaned


def dedupe_and_clean_skills(rows: list[Skill]) -> list[Skill]:
    """Remove duplicate skills and clean noisy entries."""
    cleaned: list[Skill] = []
    seen: set[str] = set()

    for row in rows:
        # Skip if no name
        if not row.name or not (row.name or "").strip():
            continue
        
        name = (row.name or "").strip()
        if len(name) < 2:
            continue
        
        # Normalize proficiency_level
        proficiency = (row.proficiency_level or "").strip() if row.proficiency_level else None
        if proficiency and proficiency.lower() in ["unknown", "n/a", "undefined", ""]:
            proficiency = None
        
        # Validate years_of_experience
        years = row.years_of_experience
        if years is not None and years < 0:
            years = None
        
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        
        cleaned.append(Skill(
            name=name,
            proficiency_level=proficiency,
            years_of_experience=years
        ))

    return cleaned


class CVExtractorService:
    def __init__(self, ollama_host: str = "http://localhost:11434", model: str = "llama3.1"):
        self.model = model
        base_url = f"{ollama_host.rstrip('/')}/v1"
        self._base_client = OpenAI(base_url=base_url, api_key="ollama")
        self.client = instructor.from_openai(self._base_client, mode=instructor.Mode.JSON)

    def _extract_pass(self, prompt: str) -> CVExtractionResult:
        """Extract with robust error handling for model endpoint unavailability."""
        try:
            return self.client.chat.completions.create(
                model=self.model,
                response_model=CVExtractionResult,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You extract structured CV data into JSON. "
                            "Prefer factual values from the text. "
                            "Leave unknown values as null or empty arrays."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                extra_body={"options": {"num_ctx": 2048, "temperature": 0, "num_gpu": 1}},
            )
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(f"Model endpoint unavailable: {str(e)}. Returning empty result.")
            # Return empty extraction result - will be merged/deduped gracefully
            return CVExtractionResult(candidate=Candidate())
        except Exception as e:
            logger.error(f"Unexpected extraction error: {str(e)}. Returning empty result.")
            return CVExtractionResult(candidate=Candidate())

    def extract(self, cv_text: str) -> Candidate:
        """
        Two-pass extraction with quality control:
        - Pass A: Strict extraction with format validation
        - Pass B: Fallback/recovery extraction
        - Merge with deduplication and cleaning
        """
        try:
            # Pass A: focused extraction to boost precision on key headings.
            pass_a_prompt = f"""
Extract ALL Candidate information including:
- Personal Information / Profile / Contact (name: string, email: string)
- Education / Academic Background (list of: degree, institution, year as 4-digit int, cgpa as float)
- Experience / Employment (list of: job_title, organization, location, start_date, end_date, is_current as bool)
- Publications / Research Output (list of: title, authors as LIST OF STRINGS ONLY (e.g. ['John Smith', 'Jane Doe']), venue as string (NOT number), year as 4-digit int)
- Skills / Technical Skills (list of: name, proficiency_level, years_of_experience as float)
- Patents / Inventions (list of: title, inventors as LIST OF STRINGS ONLY, patent_no, year, status)
- Books / Book Authorship (list of: title, authors as LIST OF STRINGS ONLY, publisher, year, isbn)
- Supervision / Student Mentoring (list of: level, student_name, year)

CRITICAL RULES:
- Authors MUST be strings ONLY, never objects. Format: ['First Author', 'Second Author']
- Venue MUST be a string, NEVER a number. Examples: 'IEEE Transactions on Software', 'ACM SIGMOD 2023'
- Year fields MUST be 4-digit integers (2023), NOT other formats
- Do NOT include placeholder values like 'N/A', 'TBD', 'Not specified', 'Unknown'
- Leave null/empty if not found - prefer empty over placeholder

Section Detection Tips:
- Look for section headings: Education, Experience, Publications, Skills, Patents, Books, Supervision
- Extract ONLY factual entries with real names, dates, and titles
- Skip any entry that appears to be an example or placeholder

CV text:
{cv_text}
""".strip()

            pass_a = self._extract_pass(pass_a_prompt).candidate
            logger.info(f"Pass A extracted: {len(pass_a.publications)} publications, {len(pass_a.education)} education, {len(pass_a.experience)} experience")

        except Exception as e:
            logger.warning(f"Pass A extraction failed: {str(e)}")
            pass_a = Candidate()

        try:
            # Pass B: full-text fallback to recover data pass A may miss.
            pass_b_prompt = f"""
Extract from CV text: Candidate name, email, summary, education, experience, publications, skills, patents, books, and supervision records.
This is a RECOVERY pass - capture any entries missed in the first pass.

STRICT FORMATTING:
- publications[].authors: LIST OF STRINGS ['Author 1', 'Author 2'], NOT [{{'name': 'Author'}}]
- publications[].venue: STRING like 'IEEE Journal', NEVER integer/number
- years: 4-digit integers like 2023, NEVER '2023.0' or 'fiscal 2023'
- job dates: plain text 'Jan 2020' or 'Present', not objects
- NO placeholder values: skip 'N/A', 'TBD', empty titles

Be thorough - extract ALL mentioned skills, publications, patents, and students.
But prefer accuracy over volume - skip anything uncertain.

CV text:
{cv_text}
""".strip()

            pass_b = self._extract_pass(pass_b_prompt).candidate
            logger.info(f"Pass B extracted: {len(pass_b.publications)} publications, {len(pass_b.education)} education, {len(pass_b.experience)} experience")

        except Exception as e:
            logger.warning(f"Pass B extraction failed: {str(e)}")
            pass_b = Candidate()

        # Merge with quality control
        merged = self._merge_candidates(pass_a, pass_b)
        
        # Clean and deduplicate each section for quality control
        merged.education = dedupe_education_rows(merged.education)
        merged.publications = dedupe_and_clean_publications(merged.publications)
        merged.experience = dedupe_and_clean_experience(merged.experience)
        merged.patents = dedupe_and_clean_patents(merged.patents)
        merged.books = dedupe_and_clean_books(merged.books)
        merged.skills = dedupe_and_clean_skills(merged.skills)
        
        logger.info(f"Final output: {len(merged.publications)} publications, {len(merged.education)} education, {len(merged.experience)} experience, {len(merged.patents)} patents, {len(merged.books)} books, {len(merged.skills)} skills")
        
        return merged

    def _merge_candidates(self, primary: Candidate, fallback: Candidate) -> Candidate:
        merged = Candidate(
            name=primary.name or fallback.name,
            email=primary.email or fallback.email,
            summary=primary.summary or fallback.summary,
            education=[*primary.education, *fallback.education],
            experience=[*primary.experience, *fallback.experience],
            publications=[*primary.publications, *fallback.publications],
            skills=[*primary.skills, *fallback.skills],
            patents=[*primary.patents, *fallback.patents],
            books=[*primary.books, *fallback.books],
            supervision=[*primary.supervision, *fallback.supervision],
        )

        return merged


def extract_candidate_from_text(cv_text: str, **kwargs: Any) -> Candidate:
    service = CVExtractorService(**kwargs)
    return service.extract(cv_text)
