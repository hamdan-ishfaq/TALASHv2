#!/usr/bin/env python3
"""
Export TALASH relational data to milestone CSV outputs.

Output files:
- ../csv_exports/000_SUMMARY.csv
- ../csv_exports/001_candidates.csv
- ../csv_exports/002_education_records.csv
- ../csv_exports/003_work_experiences.csv
- ../csv_exports/004_publications.csv
- ../csv_exports/005_skills.csv
- ../csv_exports/006_patents.csv
- ../csv_exports/007_books.csv
- ../csv_exports/008_supervision_records.csv
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import csv

from app.db import SessionLocal
from app.models.models import (
    Candidate,
    EducationRecord,
    WorkExperience,
    JournalPublication,
    ConferencePublication,
    Skill,
    Patent,
    Book,
    SupervisionRecord,
)


def _date_to_text(value: date | None) -> str:
    return value.isoformat() if value else ""


def export_all() -> Path:
    script_dir = Path(__file__).resolve().parent
    output_dir = (script_dir.parent / "csv_exports").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        candidates = db.query(Candidate).order_by(Candidate.id).all()

        cand_name = {c.id: c.name for c in candidates}
        edu = db.query(EducationRecord).order_by(EducationRecord.id).all()
        work = db.query(WorkExperience).order_by(WorkExperience.id).all()
        jp = db.query(JournalPublication).order_by(JournalPublication.id).all()
        cp = db.query(ConferencePublication).order_by(ConferencePublication.id).all()
        skills = db.query(Skill).order_by(Skill.id).all()
        patents = db.query(Patent).order_by(Patent.id).all()
        books = db.query(Book).order_by(Book.id).all()
        supervision = db.query(SupervisionRecord).order_by(SupervisionRecord.id).all()

        # 001 candidates
        with (output_dir / "001_candidates.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "ID", "Name", "Email", "Status", "File Path", "Raw Text Length", "Summary Length"
            ])
            for c in candidates:
                w.writerow([
                    c.id,
                    c.name or "",
                    c.email or "",
                    c.status or "",
                    c.file_path or "",
                    len(c.raw_text or ""),
                    len(c.summary or ""),
                ])

        # 002 education
        with (output_dir / "002_education_records.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "ID", "Candidate ID", "Candidate Name", "Stage", "Degree Title", "Specialization",
                "Institution", "Start Year", "End Year", "Marks %", "CGPA", "CGPA Scale",
                "Gap Before Start (Months)", "Gap Justified By Experience"
            ])
            for r in edu:
                w.writerow([
                    r.id,
                    r.candidate_id,
                    cand_name.get(r.candidate_id, ""),
                    r.stage or "",
                    r.degree_title or "",
                    r.specialization or "",
                    r.institution or "",
                    r.start_year or "",
                    r.end_year or "",
                    r.marks_percentage or "",
                    r.cgpa or "",
                    r.cgpa_scale or "",
                    r.gap_before_start_months or "",
                    "Yes" if r.gap_justified_by_experience else "No",
                ])

        # 003 work
        with (output_dir / "003_work_experiences.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "ID", "Candidate ID", "Candidate Name", "Job Title", "Organization", "Location",
                "Employment Type", "Start Date", "End Date", "Is Current", "Academic Role",
                "Overlaps With Education"
            ])
            for r in work:
                w.writerow([
                    r.id,
                    r.candidate_id,
                    cand_name.get(r.candidate_id, ""),
                    r.job_title or "",
                    r.organization or "",
                    r.location or "",
                    r.employment_type or "",
                    _date_to_text(r.start_date),
                    _date_to_text(r.end_date),
                    "Yes" if r.is_current else "No",
                    "Yes" if r.is_academic_role else "No",
                    "Yes" if r.overlaps_with_education else "No",
                ])

        # 004 publications (journals + conferences)
        with (output_dir / "004_publications.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "ID", "Candidate ID", "Candidate Name", "Type", "Title", "Venue", "Year", "Authors",
                "ISSN", "Indexed", "Ranking", "Impact/Core", "Authorship Role", "Author Position", "Topic"
            ])
            for r in jp:
                indexed = []
                if r.wos_indexed:
                    indexed.append("WoS")
                if r.scopus_indexed:
                    indexed.append("Scopus")
                w.writerow([
                    r.id,
                    r.candidate_id,
                    cand_name.get(r.candidate_id, ""),
                    "journal",
                    r.title or "",
                    r.journal_name or "",
                    r.year or "",
                    r.authors or "",
                    r.issn or "",
                    ",".join(indexed),
                    r.quartile or "",
                    r.impact_factor or "",
                    r.authorship_role or "",
                    r.author_position or "",
                    r.topic_category or "",
                ])
            for r in cp:
                w.writerow([
                    r.id,
                    r.candidate_id,
                    cand_name.get(r.candidate_id, ""),
                    "conference",
                    r.title or "",
                    r.conference_name or "",
                    r.year or "",
                    r.authors or "",
                    "",
                    r.indexed_in or "",
                    r.core_ranking or ("A*" if r.is_a_star else "Unranked"),
                    r.conference_series or "",
                    r.authorship_role or "",
                    r.author_position or "",
                    r.topic_category or "",
                ])

        # 005 skills
        with (output_dir / "005_skills.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "ID", "Candidate ID", "Candidate Name", "Skill", "Category",
                "Evidenced In Work", "Evidenced In Research", "Strength Of Evidence"
            ])
            for r in skills:
                w.writerow([
                    r.id,
                    r.candidate_id,
                    cand_name.get(r.candidate_id, ""),
                    r.name or "",
                    r.category or "",
                    "Yes" if r.evidenced_in_work else "No",
                    "Yes" if r.evidenced_in_research else "No",
                    r.strength_of_evidence or "",
                ])

        # 006 patents
        with (output_dir / "006_patents.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "ID", "Candidate ID", "Candidate Name", "Patent No", "Title", "Inventors",
                "Date Filed", "Country Of Filing", "Status", "Inventor Role", "Online Link"
            ])
            for r in patents:
                w.writerow([
                    r.id,
                    r.candidate_id,
                    cand_name.get(r.candidate_id, ""),
                    r.patent_no or "",
                    r.title or "",
                    r.inventors or "",
                    _date_to_text(r.date_filed),
                    r.country_of_filing or "",
                    r.status or "",
                    r.inventor_role or "",
                    r.online_link or "",
                ])

        # 007 books
        with (output_dir / "007_books.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "ID", "Candidate ID", "Candidate Name", "Title", "Authors", "ISBN",
                "Publisher", "Year", "Authorship Role", "Online Link"
            ])
            for r in books:
                w.writerow([
                    r.id,
                    r.candidate_id,
                    cand_name.get(r.candidate_id, ""),
                    r.title or "",
                    r.authors or "",
                    r.isbn or "",
                    r.publisher or "",
                    r.year or "",
                    r.authorship_role or "",
                    r.online_link or "",
                ])

        # 008 supervision
        with (output_dir / "008_supervision_records.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "ID", "Candidate ID", "Candidate Name", "Level", "Student Name", "Year",
                "Supervision Role", "Publications With Student"
            ])
            for r in supervision:
                w.writerow([
                    r.id,
                    r.candidate_id,
                    cand_name.get(r.candidate_id, ""),
                    r.student_level or "",
                    r.student_name or "",
                    r.completion_year or "",
                    r.supervision_role or "",
                    r.publications_with_student or 0,
                ])

        # 000 summary
        edu_by = {}
        work_by = {}
        pubs_by = {}
        skills_by = {}
        patents_by = {}
        books_by = {}
        sup_by = {}

        for r in edu:
            edu_by[r.candidate_id] = edu_by.get(r.candidate_id, 0) + 1
        for r in work:
            work_by[r.candidate_id] = work_by.get(r.candidate_id, 0) + 1
        for r in jp:
            pubs_by[r.candidate_id] = pubs_by.get(r.candidate_id, 0) + 1
        for r in cp:
            pubs_by[r.candidate_id] = pubs_by.get(r.candidate_id, 0) + 1
        for r in skills:
            skills_by[r.candidate_id] = skills_by.get(r.candidate_id, 0) + 1
        for r in patents:
            patents_by[r.candidate_id] = patents_by.get(r.candidate_id, 0) + 1
        for r in books:
            books_by[r.candidate_id] = books_by.get(r.candidate_id, 0) + 1
        for r in supervision:
            sup_by[r.candidate_id] = sup_by.get(r.candidate_id, 0) + 1

        with (output_dir / "000_SUMMARY.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "Candidate ID", "Name", "Status", "Education", "Work", "Publications", "Skills",
                "Patents", "Books", "Supervision", "TOTAL RECORDS"
            ])
            for c in candidates:
                total = (
                    edu_by.get(c.id, 0)
                    + work_by.get(c.id, 0)
                    + pubs_by.get(c.id, 0)
                    + skills_by.get(c.id, 0)
                    + patents_by.get(c.id, 0)
                    + books_by.get(c.id, 0)
                    + sup_by.get(c.id, 0)
                )
                w.writerow([
                    c.id,
                    c.name or "",
                    c.status or "",
                    edu_by.get(c.id, 0),
                    work_by.get(c.id, 0),
                    pubs_by.get(c.id, 0),
                    skills_by.get(c.id, 0),
                    patents_by.get(c.id, 0),
                    books_by.get(c.id, 0),
                    sup_by.get(c.id, 0),
                    total,
                ])

        return output_dir
    finally:
        db.close()


if __name__ == "__main__":
    target = export_all()
    print(f"CSV export complete: {target}")
