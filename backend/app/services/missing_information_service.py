from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.models import (
    Book,
    Candidate,
    ConferencePublication,
    JournalPublication,
    MissingInformationRequest,
    Patent,
    Skill,
    SupervisionRecord,
)

logger = logging.getLogger(__name__)


DEFAULT_MODULES: tuple[str, ...] = (
    "research_analysis",
    "patents",
    "books",
    "supervision",
    "skills",
)


@dataclass(frozen=True)
class MissingInfoGenerateResult:
    candidate_id: int
    generated_modules: list[str]


def _normalize_modules(modules: Iterable[str] | None) -> list[str]:
    if not modules:
        return list(DEFAULT_MODULES)
    out: list[str] = []
    for module in modules:
        m = (module or "").strip().lower()
        if not m:
            continue
        out.append(m)
    return out


def _has_signal(text: str, patterns: list[str]) -> bool:
    if not text:
        return False
    for pat in patterns:
        if re.search(pat, text, flags=re.IGNORECASE):
            return True
    return False


def _upsert_missing_info_request(
    db: Session,
    *,
    candidate_id: int,
    module_name: str,
    missing_fields: list[str],
    subject: str,
    body: str,
) -> None:
    existing = (
        db.query(MissingInformationRequest)
        .filter_by(candidate_id=candidate_id, module_name=module_name)
        .first()
    )
    if existing:
        existing.missing_fields_json = json.dumps(missing_fields)
        existing.draft_email_subject = subject
        existing.draft_email_body = body
        existing.status = "draft"
    else:
        db.add(
            MissingInformationRequest(
                candidate_id=candidate_id,
                module_name=module_name,
                missing_fields_json=json.dumps(missing_fields),
                draft_email_subject=subject,
                draft_email_body=body,
                status="draft",
            )
        )


def _build_email(candidate_name: str | None, module_name: str, missing_fields: list[str]) -> tuple[str, str]:
    display_name = (candidate_name or "Candidate").strip() or "Candidate"

    pretty_module = module_name.replace("_", " ").title()
    subject = f"Request for additional information ({pretty_module})"

    bullets = "\n".join(f"- {f.replace('_', ' ')}" for f in missing_fields)
    body = (
        f"Hello {display_name},\n\n"
        f"To complete your profile review, we need a few additional details for: {pretty_module}.\n\n"
        f"Please provide the following:\n{bullets}\n\n"
        "Thanks,\n"
        "TALASH Team\n"
    )
    return subject, body


def generate_missing_information_requests(
    db: Session,
    candidate_id: int,
    *,
    modules: Iterable[str] | None = None,
    force: bool = False,
) -> MissingInfoGenerateResult:
    """Generate missing-info requests without any LLM calls.

    - When force=False (default), requests are created only when we detect a textual
      signal in candidate.raw_text *and* the corresponding normalized table is empty.
    - When force=True, requests are created for empty tables even without signals.

    This function upserts `MissingInformationRequest` rows per (candidate_id, module_name).
    Caller is responsible for committing.
    """

    cand = db.query(Candidate).filter_by(id=candidate_id).first()
    if not cand:
        raise ValueError(f"Candidate {candidate_id} not found")

    normalized_modules = _normalize_modules(modules)
    raw_text = cand.raw_text or ""

    generated: list[str] = []

    def maybe_generate(module_name: str, *, is_empty: bool, signals: list[str], missing_fields: list[str]) -> None:
        if not is_empty:
            return
        if (not force) and (not _has_signal(raw_text, signals)):
            return
        subject, body = _build_email(cand.name, module_name, missing_fields)
        _upsert_missing_info_request(
            db,
            candidate_id=candidate_id,
            module_name=module_name,
            missing_fields=missing_fields,
            subject=subject,
            body=body,
        )
        generated.append(module_name)

    if "research_analysis" in normalized_modules:
        pub_count = (
            db.query(JournalPublication.id).filter_by(candidate_id=candidate_id).count()
            + db.query(ConferencePublication.id).filter_by(candidate_id=candidate_id).count()
        )
        maybe_generate(
            "research_analysis",
            is_empty=(pub_count == 0),
            signals=[r"\bpublication(s)?\b", r"\bjournal\b", r"\bconference\b", r"\bdoi\b"],
            missing_fields=["publications_list", "google_scholar_link", "orcid"],
        )

    if "patents" in normalized_modules:
        patent_count = db.query(Patent.id).filter_by(candidate_id=candidate_id).count()
        maybe_generate(
            "patents",
            is_empty=(patent_count == 0),
            signals=[r"\bpatent(s)?\b", r"\bapplication no\.?\b"],
            missing_fields=["patents_list"],
        )

    if "books" in normalized_modules:
        book_count = db.query(Book.id).filter_by(candidate_id=candidate_id).count()
        maybe_generate(
            "books",
            is_empty=(book_count == 0),
            signals=[r"\bisbn\b", r"\bbook(s)?\b", r"\bbook chapter\b"],
            missing_fields=["books_and_chapters_list"],
        )

    if "supervision" in normalized_modules:
        sup_count = db.query(SupervisionRecord.id).filter_by(candidate_id=candidate_id).count()
        maybe_generate(
            "supervision",
            is_empty=(sup_count == 0),
            signals=[r"\bsupervis", r"\bphd\b", r"\bthesis\b", r"\bms\b"],
            missing_fields=["supervision_records"],
        )

    if "skills" in normalized_modules:
        skills_count = db.query(Skill.id).filter_by(candidate_id=candidate_id).count()
        maybe_generate(
            "skills",
            is_empty=(skills_count == 0),
            signals=[r"\bskills\b", r"\bexpertise\b", r"\bcompetenc"],
            missing_fields=["skills_list"],
        )

    if generated:
        logger.info(
            "[MissingInfo] Generated/updated %d missing-info requests for candidate_id=%d: %s",
            len(generated),
            candidate_id,
            generated,
        )

    return MissingInfoGenerateResult(candidate_id=candidate_id, generated_modules=generated)
