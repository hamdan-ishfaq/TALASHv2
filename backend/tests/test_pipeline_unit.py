"""Unit tests for TALASH post-extraction pipeline helpers (no live LLM / no Docker)."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.models import (
    Base,
    Candidate,
    CollaborationEdge,
    ConferencePublication,
    JournalPublication,
    SupervisionRecord,
)
from app.services.collaboration_analysis import run_collaboration_analysis
from app.services.pipeline import run_local_ip_format_checks
from app.services.supervision_analysis import run_supervision_analysis
from app.services.topic_analysis import run_topic_analysis


def _memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_topic_analysis_heuristic_buckets():
    db = _memory_session()
    c = Candidate(name="Alice Researcher", status="completed")
    db.add(c)
    db.commit()
    db.refresh(c)
    db.add(
        JournalPublication(
            candidate_id=c.id,
            title="Deep Learning for Medical Image Segmentation",
            authors="Alice Researcher, Bob",
            journal_name="IEEE Access",
            year=2024,
        )
    )
    db.add(
        ConferencePublication(
            candidate_id=c.id,
            title="A Survey on Network Security Protocols",
            authors="Alice Researcher, Carol",
            conference_name="IEEE ICC",
            year=2023,
        )
    )
    db.commit()

    r = run_topic_analysis(db, c.id)
    assert r.publication_count == 2
    assert r.diversity_score > 0
    assert r.dominant_theme is not None


def test_collaboration_recurring_flag():
    db = _memory_session()
    c = Candidate(name="Lead Author", status="completed")
    db.add(c)
    db.commit()
    db.refresh(c)
    j = JournalPublication(
        candidate_id=c.id,
        title="Paper One",
        authors="Lead Author, Same Colleague",
        journal_name="J1",
        year=2020,
    )
    db.add(j)
    db.flush()
    db.add(
        CollaborationEdge(
            candidate_id=c.id,
            coauthor_name="Same Colleague",
            publication_id=j.id,
            publication_type="journal",
            edge_weight=1.0,
            is_recurring=False,
        )
    )
    db.add(
        CollaborationEdge(
            candidate_id=c.id,
            coauthor_name="Same Colleague",
            publication_id=j.id,
            publication_type="journal",
            edge_weight=1.0,
            is_recurring=False,
        )
    )
    db.commit()

    out = run_collaboration_analysis(db, c.id)
    assert out.recurring_collaborators >= 1
    edges = db.query(CollaborationEdge).filter_by(candidate_id=c.id).all()
    assert all(e.is_recurring for e in edges)


def test_supervision_links_publications():
    db = _memory_session()
    c = Candidate(name="Prof X", status="completed")
    db.add(c)
    db.commit()
    db.refresh(c)
    db.add(
        SupervisionRecord(
            candidate_id=c.id,
            student_level="MS",
            student_name="Student One",
            supervision_role="Main Supervisor",
            publications_with_student=0,
        )
    )
    db.add(
        JournalPublication(
            candidate_id=c.id,
            title="Joint Work",
            authors="Prof X, Student One",
            journal_name="JRNL",
            year=2022,
        )
    )
    db.commit()

    run_supervision_analysis(db, c.id)
    rec = db.query(SupervisionRecord).filter_by(candidate_id=c.id).first()
    assert (rec.publications_with_student or 0) >= 1


def test_isbn_patent_format_checks():
    from app.models.models import Book, Patent

    db = _memory_session()
    c = Candidate(name="T", status="completed")
    db.add(c)
    db.commit()
    db.refresh(c)
    db.add(Book(candidate_id=c.id, title="Test Book", isbn="9780000000002"))
    db.add(Patent(candidate_id=c.id, title="P", patent_no="US10123456B2"))
    db.commit()

    r = run_local_ip_format_checks(db, c.id)
    assert r["books_with_valid_isbn"] == 1
    assert r["patents_with_plausible_number"] == 1
