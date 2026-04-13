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


class Candidate(BaseModel):
    name: str | None = None
    email: str | None = None
    summary: str | None = None
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)


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
            extra_body={"options": {"num_ctx": 4096, "temperature": 0}},
        )

    def extract(self, cv_text: str) -> Candidate:
        # Pass A: focused extraction to boost precision on key headings.
        pass_a_prompt = f"""
Extract Candidate, Education, Experience, and Publication details.
Focus first on these headings (if present):
- Personal Information / Profile / Contact
- Education / Academic Background
- Experience / Employment / Professional Experience
- Publications / Research Output

Return only fields represented by the response schema.

CV text:
{cv_text}
""".strip()

        pass_a = self._extract_pass(pass_a_prompt).candidate

        # Pass B: full-text fallback to recover data pass A may miss.
        pass_b_prompt = f"""
Extract Candidate, Education, Experience, and Publication details from the full CV text.
Use this as a fallback pass to capture any missing fields.

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
        )

        return merged


def extract_candidate_from_text(cv_text: str, **kwargs: Any) -> Candidate:
    service = CVExtractorService(**kwargs)
    return service.extract(cv_text)
