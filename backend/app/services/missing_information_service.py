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
    EducationRecord,
    JournalPublication,
    MissingInformationRequest,
    Patent,
    Skill,
    SupervisionRecord,
    WorkExperience,
)

logger = logging.getLogger(__name__)


DEFAULT_MODULES: tuple[str, ...] = (
    "education_analysis",
    "experience_analysis",
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
        "If any item does not apply, reply with a short note so we can mark it as not applicable.\n\n"
        "Please reply with the missing details or attach an updated CV.\n\n"
        "Thanks,\n"
        "TALASH Team\n"
    )
    return subject, body


def _education_missing_labels(db: Session, candidate_id: int) -> list[str]:
    labels: list[str] = []
    for rec in db.query(EducationRecord).filter_by(candidate_id=candidate_id).all():
        stage = (rec.stage or "").upper()
        label_bits: list[str] = []
        if stage in ("SSE", "HSSC", "MATRIC", "INTERMEDIATE", "O-LEVEL", "A-LEVEL"):
            if rec.marks_percentage is None and rec.cgpa is None:
                label_bits.append("marks or percentage")
        elif stage in ("UG", "PG", "PHD", "BS", "MS", "MSC", "MPHIL", "BSC", "OTHER") or (rec.degree_title or "").strip():
            if rec.cgpa is None and rec.marks_percentage is None and rec.normalized_cgpa is None:
                label_bits.append("CGPA or percentage")
            if rec.cgpa is not None and (rec.cgpa_scale is None or rec.cgpa_scale <= 0):
                label_bits.append("CGPA scale (e.g. 4.0)")
        if not (rec.institution or "").strip() and not (rec.board_or_university or "").strip():
            label_bits.append("institution or board name")
        if rec.start_year is None and rec.end_year is None:
            label_bits.append("start or end year")
        if label_bits:
            who = rec.degree_title or rec.stage or "education entry"
            labels.append(f"{who}: " + ", ".join(sorted(set(label_bits))))
    return list(dict.fromkeys(labels))


def _experience_missing_labels(db: Session, candidate_id: int) -> list[str]:
    labels: list[str] = []
    for w in db.query(WorkExperience).filter_by(candidate_id=candidate_id).all():
        title = (w.job_title or "Role").strip()
        missing: list[str] = []
        if w.start_date is None and w.start_year is None:
            missing.append("start date")
        if not w.is_current and w.end_date is None and w.end_year is None:
            missing.append("end date or mark role as current")
        if missing:
            labels.append(f"{title}: " + ", ".join(missing))
    return list(dict.fromkeys(labels))


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

    if "education_analysis" in normalized_modules:
        edu_labels = _education_missing_labels(db, candidate_id)
        if edu_labels:
            subject, body = _build_email(cand.name, "education_analysis", edu_labels)
            _upsert_missing_info_request(
                db,
                candidate_id=candidate_id,
                module_name="education_analysis",
                missing_fields=edu_labels,
                subject=subject,
                body=body,
            )
            generated.append("education_analysis")

    if "experience_analysis" in normalized_modules:
        exp_labels = _experience_missing_labels(db, candidate_id)
        if exp_labels:
            subject, body = _build_email(cand.name, "experience_analysis", exp_labels)
            _upsert_missing_info_request(
                db,
                candidate_id=candidate_id,
                module_name="experience_analysis",
                missing_fields=exp_labels,
                subject=subject,
                body=body,
            )
            generated.append("experience_analysis")

    if generated:
        logger.info(
            "[MissingInfo] Generated/updated %d missing-info requests for candidate_id=%d: %s",
            len(generated),
            candidate_id,
            generated,
        )

    return MissingInfoGenerateResult(candidate_id=candidate_id, generated_modules=generated)
