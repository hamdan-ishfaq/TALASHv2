from __future__ import annotations

from typing import Any

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field


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


class CVExtractorService:
    def __init__(self, ollama_host: str = "http://localhost:11434", model: str = "llama3.1"):
        self.model = model
        base_url = f"{ollama_host.rstrip('/')}/v1"
        self._base_client = OpenAI(base_url=base_url, api_key="ollama")
        self.client = instructor.from_openai(self._base_client, mode=instructor.Mode.JSON)

    def _extract_pass(self, prompt: str) -> CVExtractionResult:
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

    def extract(self, cv_text: str) -> Candidate:
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

CRITICAL: 
- Authors MUST be strings ONLY, never objects. Format: ['First Author', 'Second Author']
- Venue MUST be a string, NEVER a number
- Year fields MUST be 4-digit integers (2023), NOT other formats
- Leave null/empty if not found

Focus first on these section headings:
- Personal Information / Profile
- Education / Academic Background
- Experience / Employment
- Publications / Research Output
- Skills / Technical Skills
- Patents / Inventions
- Books / Book Authorship
- Supervision / Student Mentoring

CV text:
{cv_text}
""".strip()

        pass_a = self._extract_pass(pass_a_prompt).candidate

        # Pass B: full-text fallback to recover data pass A may miss.
        pass_b_prompt = f"""
Extract from CV text: Candidate name, email, summary, education, experience, publications, skills, patents, books, and supervision records.
Use this as a fallback pass to capture ANY missing fields from Pass A.

SCHEMA FORMAT REQUIREMENTS:
- publications[].authors: LIST OF STRINGS ['Author 1', 'Author 2'], NOT [{{'name': 'Author'}}]
- publications[].venue: STRING like 'IEEE Journal', NEVER integer/number
- years: 4-digit integers like 2023, NOT decimals or text
- all other string fields: plain text, NOT nested objects

Be thorough - extract ALL mentioned skills, publications, patents, and students.

CV text:
{cv_text}
""".strip()

        pass_b = self._extract_pass(pass_b_prompt).candidate

        merged = self._merge_candidates(pass_a, pass_b)
        merged.education = dedupe_education_rows(merged.education)
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
